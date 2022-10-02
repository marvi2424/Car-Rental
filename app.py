import os
import stripe

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_session import Session
from cs50 import SQL
import datetime
from datetime import date, timedelta
from helpers import (
    compare_dates,
    strdate,
    strdate_to_d,
    euro,
    total_Days,
    is_date,
)
from dateutil.relativedelta import relativedelta
import time


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["Templates_Auto_Reload"] = True

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=5)
Session(app)

# Configure CS50 library to use database

uri = os.getenv("DATABASE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://")
db = SQL(uri)

# Custom filter
app.jinja_env.filters["date"] = strdate_to_d
app.jinja_env.filters["euro"] = euro

# Pass function to jinja
app.jinja_env.globals.update(len=len)


# Check if environment variables are set
if not os.environ.get("STRIPE_PUBLIC_KEY"):
    raise RuntimeError("STRIPE_PUBLIC_KEY not set")

elif not os.environ.get("STRIPE_PUBLIC_KEY"):
    raise RuntimeError("STRIPE_PRIVATE_KEY not set")

elif not os.environ.get("PRICE_ID"):
    raise RuntimeError("PRICE_ID not set")

elif not os.environ.get("ENDPOINT_SECRET"):
    raise RuntimeError("ENDPOINT_SECRET not set")

# Set stripe private key
stripe.api_key = os.environ.get("STRIPE_PRIVATE_KEY")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/cars", methods=["GET", "POST"])
def cars():

    # If user comes back from create-checkout-session
    if "checkout_id" in session:
        db.execute(
            "DELETE FROM pending_bookings WHERE checkout_id = ?", session["checkout_id"]
        )

    # Delete rows from active booking table when release date has passed
    now = datetime.datetime.now()
    year = now.year
    month = now.month
    day = now.day
    hour = now.hour

    # Convert date to yyyymmdd str format to run sql queries
    if month < 10:
        current_date = str(year) + "0" + str(month) + str(day)
    else:
        current_date = str(year) + str(month) + str(day)

    db.execute(
        "DELETE FROM active_bookings WHERE returndate  <= ? AND releasehour < ?",
        current_date,
        hour,
    )

    # Min and max date
    max_date_p = date.today() + relativedelta(months=+1, days=+1)
    min_date_p = date.today() + relativedelta(days=+1)

    max_date_r = date.today() + relativedelta(months=+1, days=+2)
    min_date_r = date.today() + relativedelta(days=+2)

    # If user reaches via POST
    if request.method == "POST":

        # Get car id that the user wants to reserve
        car_id = request.form.get("car_id")

        # Redirect if user submits form without complete input
        if not car_id:
            return redirect("/cars")

        session["car_id"] = car_id

        # Check if the car id is in database (the user can change the id input with dev tools)
        car = db.execute("SELECT * FROM cars WHERE id = ?", car_id)

        if len(car) != 1:
            flash("ERROR")
            cars = db.execute(
                "SELECT * FROM cars WHERE id NOT IN (SELECT car_id FROM active_bookings)"
            )

            return render_template("cars.html", cars=cars)

        # Redirect to book page
        return redirect("/book")

    # Via Get
    else:
        # Get pickup and release date
        pickupdate = request.args.get("pickupdate")
        returndate = request.args.get("returndate")

        # Redirect if user submits form without complete input
        if not pickupdate or not returndate:
            cars = db.execute(
                "SELECT * FROM cars WHERE id NOT IN (SELECT car_id FROM active_bookings)"
            )
            return render_template(
                "cars.html",
                cars=cars,
                min_date_p=min_date_p,
                max_date_p=max_date_p,
                max_date_r=max_date_r,
                min_date_r=min_date_r,
            )

        # Check if date is valid
        if pickupdate and returndate:
            if not is_date(pickupdate) or not is_date(returndate):
                flash("Not a valid date")
                return redirect("/cars")

        # If user submits date form check for avaiable cars

        bool_min_p = compare_dates(min_date_p, pickupdate)
        bool_max_p = compare_dates(max_date_p, pickupdate)
        bool_min_r = compare_dates(min_date_r, returndate)
        bool_max_r = compare_dates(max_date_r, returndate)

        # Error checking
        if compare_dates(str(pickupdate), returndate) == 0:
            flash("Returndate must be after pickupdate")
            return redirect("/cars")

        elif bool_min_p == 0 or bool_max_p == 1 or bool_min_r == 0 or bool_max_r == 1:
            flash("Incorrect Date!")
            return redirect("/cars")

        elif total_Days(pickupdate, returndate) <= 0:
            flash("You must reserve for at least one day")
            return redirect("/cars")

        # Check for available dates
        available_cars = db.execute(
            "SELECT * FROM cars WHERE id NOT IN (SELECT car_id FROM active_bookings WHERE (? >= pickupdate AND ? <= returndate) OR (? >= pickupdate AND ? <= returndate))",
            strdate(pickupdate),
            strdate(pickupdate),
            strdate(returndate),
            strdate(returndate),
        )

        if len(available_cars) == 0:
            flash("No availble cars for these dates")
            return redirect("/cars")

        return render_template(
            "cars.html",
            cars=available_cars,
            min_date_p=min_date_p,
            max_date_p=max_date_p,
            max_date_r=max_date_r,
            min_date_r=min_date_r,
        )


@app.route("/book", methods=["GET"])
def book():

    # If user comes back from create-checkout-session
    if "checkout_id" in session:
        db.execute(
            "DELETE FROM pending_bookings WHERE checkout_id = ?", session["checkout_id"]
        )

    # Get car id
    if "car_id" not in session or len(session["car_id"]) == 0:
        return redirect("/cars")

    car_id = session["car_id"]

    max_date_p = date.today() + relativedelta(months=+1, days=+1)
    min_date_p = date.today() + relativedelta(days=+1)

    max_date_r = date.today() + relativedelta(months=+1, days=+2)
    min_date_r = date.today() + relativedelta(days=+2)

    # Via GET
    if request.method == "GET":

        # If user goes to book page without choosing a car redirect to /cars
        if not session["car_id"]:
            return redirect("/cars")

        # Get data of selected car
        car = db.execute("SELECT * FROM cars WHERE id = ?", car_id)

        if len(car) == 0:
            flash("INVALID CAR ID")
            return redirect("/cars")

        c_photos = db.execute("SELECT * FROM photos WHERE car_id = ?", car_id)

        # Check if car is booked during some periods of time
        bookings = db.execute(
            "SELECT pickupdate, returndate FROM active_bookings WHERE car_id = ? ORDER BY pickupdate ASC, returndate ASC",
            car_id,
        )

        return render_template(
            "book.html",
            c_photos=c_photos,
            car=car,
            min_date_p=min_date_p,
            max_date_p=max_date_p,
            max_date_r=max_date_r,
            min_date_r=min_date_r,
            bookings=bookings,
        )


@app.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":
        name = request.form.get("fullName")
        email = request.form.get("email")
        phonenumber = request.form.get("phonenumber")
        message = request.form.get("message")

        # Ensure that the form is completed
        if not name or not email or not phonenumber or not message:
            flash("All fields of the form must be completed if you want to contact us")
            return redirect("/contact")

        # Insert data
        db.execute(
            "INSERT INTO contact (name, email, phonenumber, message) VALUES (?, ? ,? ,?) ",
            name,
            email,
            phonenumber,
            message,
        )

        return redirect("/contact")
    else:
        return render_template("contact.html")


@app.route("/faq", methods=["GET"])
def faq():
    # Get FAQ
    requirements = db.execute("SELECT * FROM faq WHERE section = 'Requirements'")
    reservations = db.execute("SELECT * FROM faq WHERE section = 'Reservations'")
    insurance = db.execute("SELECT * FROM faq WHERE section = 'Insurance'")

    return render_template(
        "faq.html",
        requirements=requirements,
        reservations=reservations,
        insurance=insurance,
    )


@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():

    # Get the price ID
    price_id = os.environ.get("PRICE_ID")

    # Get car id
    if "car_id" not in session or len(session["car_id"]) == 0:
        return redirect("/cars")

    car_id = session["car_id"]

    # Get price of car per day
    day_price = db.execute("SELECT day_price FROM cars WHERE id = ?", car_id)

    # Max and Min date

    max_date_p = date.today() + relativedelta(months=+1, days=+1)
    min_date_p = date.today() + relativedelta(days=+1)

    max_date_r = date.today() + relativedelta(months=+1, days=+2)
    min_date_r = date.today() + relativedelta(days=+2)

    if request.method == "POST":

        # Get form fields
        name = request.form.get("fullName")
        pickupdate = request.form.get("pickupdate")
        pickuphour = request.form.get("pickuphour")
        returndate = request.form.get("returndate")
        releasehour = request.form.get("releasehour")

        # Ensure that values are submitet
        if (
            not name
            or not pickupdate
            or not pickuphour
            or not returndate
            or not releasehour
        ):
            flash("Complete the form!")
            return redirect("/book")

        # Check if pickupdate and release date are in date format(yyyy-mm-dd)
        if is_date(pickupdate) == False or is_date(returndate) == False:
            flash("Enter a valid date")
            return redirect("/book")

        # Calculate total days
        total_days = total_Days(pickupdate, returndate)
        print("-------------TOTAL DAYS--------------")
        print(total_days)

        # Check if input is invalid

        bool_min_p = compare_dates(min_date_p, pickupdate)
        bool_max_p = compare_dates(max_date_p, pickupdate)
        bool_min_r = compare_dates(min_date_r, returndate)
        bool_max_r = compare_dates(max_date_r, returndate)

        # Check if pickupdate is after than release date
        if total_days <= 0:
            flash("Returndate must be after pickupdate!")
            return redirect("/book")

        elif bool_min_p == 0 or bool_max_p == 1 or bool_min_r == 0 or bool_max_r == 1:
            flash("Incorrect Date Try Again")
            return redirect("/book")

        elif (
            int(pickuphour) < 6
            or int(pickuphour) > 23
            or int(releasehour) < 6
            or int(releasehour) > 23
        ):
            flash("Incorrect Hour")
            return redirect("/book")

        # Check if car is booked

        check = db.execute(
            "SELECT pickupdate, returndate FROM active_bookings WHERE car_id  = ? AND  ((? >= pickupdate AND ? <= returndate) OR (? >= pickupdate AND ? <= returndate))",
            car_id,
            strdate(pickupdate),
            strdate(pickupdate),
            strdate(returndate),
            strdate(returndate),
        )
        if len(check) != 0:
            for c in check:
                pdate = strdate_to_d(c["pickupdate"])
                rdate = strdate_to_d(c["returndate"])
                flash(f"Car is not available during {pdate} - {rdate} ! ")
                break

            return redirect("/book")

        # Check if car is currently being booked

        check_pending = db.execute(
            "SELECT pickupdate, returndate FROM pending_bookings WHERE car_id  = ? AND  ((? >= pickupdate AND ? <= returndate) OR (? >= pickupdate AND ? <= returndate))",
            car_id,
            strdate(pickupdate),
            strdate(pickupdate),
            strdate(returndate),
            strdate(returndate),
        )

        if len(check_pending) != 0:
            flash(
                "Oops someone is currently reserving this car in those dates.Check again after 30 minutes or pick other dates."
            )
            return redirect("/book")

        # Epoch time
        epoch = int(time.time())

        # Expire time will be 30 minutes after creation
        expires = epoch + 30 * 60

        # Get total amount
        total_amount = total_days * day_price[0]["day_price"]

        try:

            checkout_session = stripe.checkout.Session.create(
                line_items=[
                    {
                        # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                        "price": price_id,
                        "quantity": total_days,
                    },
                ],
                mode="payment",
                phone_number_collection={
                    "enabled": True,
                },
                payment_method_types=[
                    "card",
                ],
                expires_at=expires,
                success_url=url_for("thanks", _external=True),
                cancel_url=url_for("cars", _external=True),
            )

        except Exception as e:
            return str(e)

        # Insert the data in pending booking table
        db.execute(
            "INSERT INTO pending_bookings (name, pickupdate, pickuphour, returndate, releasehour, car_id, total_days, total_price, checkout_id, created) VALUES(?,?,?,?,?,?,?,?,?,?)",
            name,
            strdate(pickupdate),
            pickuphour,
            strdate(returndate),
            releasehour,
            car_id,
            total_days,
            total_amount,
            checkout_session["id"],
            checkout_session["created"],
        )

        session["checkout_id"] = checkout_session["id"]

        return redirect(checkout_session.url, code=303)


@app.route("/thanks", methods=["GET"])
def thanks():

    return render_template("thanks.html")


# Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get("STRIPE_SIGNATURE")
    endpoint_secret = os.environ.get("ENDPOINT_SECRET")
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        # invalid payload
        print("Invalid payload")
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError as e:
        # invalid signature
        print("Invalid signature")
        return "Invalid signature", 400

    # Event to dict
    event_dict = event.to_dict()

    # Checkout session completed
    if event_dict["type"] == "checkout.session.completed":

        completed = event_dict["data"]["object"]

        email = completed["customer_details"]["email"]
        phone_number = completed["customer_details"]["phone"]

        if completed["payment_status"] != "paid":
            print("NOT PAID")
            return "NOT PAID", 400

        # Get user data from pending_bookings table
        user_data = db.execute(
            "SELECT * FROM pending_bookings WHERE checkout_id = ?", completed["id"]
        )

        # Error checking
        if len(user_data) == 0:
            print("ERORR")
            return "Something went wrong", 400

        # User data
        pending_booking_id = user_data[0]["id"]
        name = user_data[0]["name"]
        pickupdate = user_data[0]["pickupdate"]
        pickuphour = user_data[0]["pickuphour"]
        returndate = user_data[0]["returndate"]
        releasehour = user_data[0]["releasehour"]
        car_id = user_data[0]["car_id"]
        total_days = user_data[0]["total_days"]
        total_price = user_data[0]["total_price"]

        prepaid_warranty = 10 * total_days

        # Insert user data into booking_history and pending_bookings
        db.execute(
            "INSERT INTO booking_history (name, email, pickupdate, pickuphour, returndate, releasehour, car_id, total_days, total_price) VALUES(?,?,?,?,?,?,?,?,?)",
            name,
            email,
            pickupdate,
            pickuphour,
            returndate,
            releasehour,
            car_id,
            total_days,
            total_price,
        )

        db.execute(
            "INSERT INTO active_bookings (name, pickupdate, pickuphour, returndate, releasehour, car_id, total_days, payment_intent, prepaid, phone_number) VALUES(?,?,?,?,?,?,?,?,?,?)",
            name,
            pickupdate,
            pickuphour,
            returndate,
            releasehour,
            car_id,
            total_days,
            completed["payment_intent"],
            prepaid_warranty,
            phone_number,
        )

        # Delete data in pending_bookings table after transaction completed
        db.execute("DELETE FROM pending_bookings WHERE id = ?", pending_booking_id)

    elif event_dict["type"] == "checkout.session.expired":
        # Delete data in pending_bookings table after sesssion expired
        session_expired = event_dict["data"]["object"]

        db.execute(
            "DELETE FROM pending_bookings WHERE checkout_id = ?", session_expired["id"]
        )

        print("checkout session expired")

    elif event_dict["type"] == "charge.succeeded":
        charge = event_dict["data"]["object"]
        print("----------------Recipt Url---------------------")
        print(charge["receipt_url"])

    elif event_dict["type"] == "payment_intent.payment_failed":
        intent = event_dict["data"]["object"]
        error_message = (
            intent["last_payment_error"]["message"]
            if intent.get("last_payment_error")
            else None
        )
        print("Failed: ", intent["id"])
        print(error_message)

    return "OK", 200
