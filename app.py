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
from helpers import compare_dates, strdate, strdate_to_d, euro, total_Days
from dateutil.relativedelta import relativedelta


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["Templates_Auto_Reload"] = True

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=1)
Session(app)

# Configure CS50 library to use Sqlite database
uri = os.getenv("DATABASE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://")
db = SQL(uri)

# Custom filter
app.jinja_env.filters["date"] = strdate_to_d
app.jinja_env.filters["euro"] = euro
# Pass function to jinja
app.jinja_env.globals.update(len=len)


if not os.environ.get("STRIPE_PUBLIC_KEY"):
    raise RuntimeError("STRIPE_PUBLIC_KEY not set")
elif not os.environ.get("STRIPE_PUBLIC_KEY"):
    raise RuntimeError("STRIPE_PRIVATE_KEY not set")
elif not os.environ.get("PRICE_ID"):
    raise RuntimeError("PRICE_ID not set")
elif not os.environ.get("ENDPOINT_SECRET"):
    raise RuntimeError("ENDPOINT_SECRET not set")


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
        "DELETE FROM active_bookings WHERE releasedate  <= ? AND releasehour < ?",
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
        releasedate = request.args.get("releasedate")

        # Redirect if user submits form without complete input
        if not pickupdate or not releasedate:
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

        # If user submits date form check for avaiable cars

        bool_min_p = compare_dates(min_date_p, pickupdate)
        bool_max_p = compare_dates(max_date_p, pickupdate)
        bool_min_r = compare_dates(min_date_r, releasedate)
        bool_max_r = compare_dates(max_date_r, releasedate)

        if compare_dates(str(pickupdate), releasedate) == 0:
            flash("Releasedate must be after pickupdate")
            return redirect("/cars")

        elif bool_min_p == 0 or bool_max_p == 1 or bool_min_r == 0 or bool_max_r == 1:
            flash("Incorrect Date!")
            return redirect("/cars")

        elif total_Days(pickupdate, releasedate) <= 0:
            flash("You must reserve for atleast one day")
            return redirect("/cars")

        available_cars = db.execute(
            "SELECT * FROM cars WHERE id NOT IN (SELECT car_id FROM active_bookings WHERE (? >= pickupdate AND ? <= releasedate) OR (? >= pickupdate AND ? <= releasedate))",
            strdate(pickupdate),
            strdate(pickupdate),
            strdate(releasedate),
            strdate(releasedate),
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
            "SELECT pickupdate, releasedate FROM active_bookings WHERE car_id = ? ORDER BY pickupdate ASC, releasedate ASC",
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
def about():

    session.clear()
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

    # Get current date and time
    now = datetime.datetime.now()
    year = now.year
    month = now.month
    day = now.day
    hour = now.hour

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
        releasedate = request.form.get("releasedate")
        releasehour = request.form.get("releasehour")

        # Ensure that values are submitet
        if (
            not name
            or not pickupdate
            or not pickuphour
            or not releasedate
            or not releasehour
        ):
            flash("Complete the form!")
            return redirect("/book")

        # Calculate total days
        total_days = total_Days(pickupdate, releasedate)
        print("-------------TOTAL DAYS--------------")
        print(total_days)

        # Check if input is invalid

        bool_min_p = compare_dates(min_date_p, pickupdate)
        bool_max_p = compare_dates(max_date_p, pickupdate)
        bool_min_r = compare_dates(min_date_r, releasedate)
        bool_max_r = compare_dates(max_date_r, releasedate)

        # Check if pickupdate is after than release date
        if total_days <= 0:
            flash("Releasedate must be after pickupdate!")
            return redirect("/book")

        elif bool_min_p == 0 or bool_max_p == 1 or bool_min_r == 0 or bool_max_r == 1:
            flash("Incorrect Date Try Again")
            return redirect("/book")

        elif (
            int(pickuphour) < 0
            or int(pickuphour) > 23
            or int(releasehour) < 0
            or int(releasehour) > 23
        ):
            flash("Incorrect Hour")
            return redirect("/book")

        # Check if car is booked

        check = db.execute(
            "SELECT pickupdate, releasedate FROM active_bookings WHERE car_id = ? AND ? >= pickupdate AND ? <= releasedate",
            car_id,
            strdate(pickupdate),
            strdate(pickupdate),
        )
        if len(check) != 0:
            for c in check:
                pdate = strdate_to_d(c["pickupdate"])
                rdate = strdate_to_d(c["releasedate"])
                flash(f"Car is not available during {pdate} - {rdate} ! ")

            return redirect("/book")

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
                success_url=url_for("thanks", _external=True),
                cancel_url=url_for("cars", _external=True),
            )

        except Exception as e:
            return str(e)

    db.execute(
        "INSERT INTO pending_bookings (name, pickupdate, pickuphour, releasedate, releasehour, car_id, total_days, total_price, checkout_id) VALUES(?,?,?,?,?,?,?,?,?)",
        name,
        strdate(pickupdate),
        pickuphour,
        strdate(releasedate),
        releasehour,
        car_id,
        total_days,
        total_amount,
        checkout_session["id"],
    )

    return redirect(checkout_session.url, code=303)


@app.route("/thanks", methods=["GET"])
def thanks():

    session.clear()
    return render_template("thanks.html")


# You can find your endpoint's secret in your webhook settings
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

    event_dict = event.to_dict()

    if event_dict["type"] == "checkout.session.completed":

        completed = event_dict["data"]["object"]
        print(completed)

        email = completed["customer_details"]["email"]
        phone_number = completed["customer_details"]["phone"]

        if completed["payment_status"] != "paid":
            print("NOT PAID")
            return "NOT PAID", 400

        user_data = db.execute(
            "SELECT * FROM pending_bookings WHERE checkout_id = ?", completed["id"]
        )

        if len(user_data) == 0:
            print("ERORR")
            return "Something went wrong", 400

        pending_booking_id = user_data[0]["id"]
        name = user_data[0]["name"]
        pickupdate = user_data[0]["pickupdate"]
        pickuphour = user_data[0]["pickuphour"]
        releasedate = user_data[0]["releasedate"]
        releasehour = user_data[0]["releasehour"]
        car_id = user_data[0]["car_id"]
        total_days = user_data[0]["total_days"]
        total_price = user_data[0]["total_price"]

        prepaid_warranty = 10 * total_days

        db.execute(
            "INSERT INTO booking_history (name, email, pickupdate, pickuphour, releasedate, releasehour, car_id, total_days, total_price) VALUES(?,?,?,?,?,?,?,?,?)",
            name,
            email,
            pickupdate,
            pickuphour,
            releasedate,
            releasehour,
            car_id,
            total_days,
            total_price,
        )

        db.execute(
            "INSERT INTO active_bookings (name, pickupdate, pickuphour, releasedate, releasehour, car_id, total_days, payment_intent, prepaid, phone_number) VALUES(?,?,?,?,?,?,?,?,?,?)",
            name,
            pickupdate,
            pickuphour,
            releasedate,
            releasehour,
            car_id,
            total_days,
            completed["payment_intent"],
            prepaid_warranty,
            phone_number,
        )

        db.execute("DELETE FROM pending_bookings WHERE id = ?", pending_booking_id)

    elif event_dict["type"] == "checkout.session.expired":
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

        # Notify the customer that payment failed

    return "OK", 200
