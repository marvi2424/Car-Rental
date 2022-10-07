import os
from random import randrange
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
from helpers import (
    compare_dates,
    strdate,
    strdate_to_d,
    euro,
    total_Days,
    is_date,
    date_limits,
    expire_checkout,
)
import time


# Configure application
app = Flask(__name__)

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
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
@expire_checkout
def index():

    return render_template("index.html")


@app.route("/check", methods=["GET"])
@expire_checkout
def check():

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
        "DELETE FROM active_reservations WHERE returndate  <= ? AND returnhour < ?",
        current_date,
        hour,
    )

    # Min and max date
    max_date_p = date_limits["max_p"]
    min_date_p = date_limits["min_p"]

    max_date_r = date_limits["max_r"]
    min_date_r = date_limits["min_r"]

    if request.method == "GET":

        # If user submits date form check for avaiable cars

        return render_template(
            "check.html",
            min_date_p=min_date_p,
            max_date_p=max_date_p,
            max_date_r=max_date_r,
            min_date_r=min_date_r,
        )


@app.route("/cars", methods=["GET", "POST"])
@expire_checkout
def cars():

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
        "DELETE FROM active_reservations WHERE returndate  <= ? AND returnhour < ?",
        current_date,
        hour,
    )

    # Min and max date
    max_date_p = date_limits["max_p"]
    min_date_p = date_limits["min_p"]

    max_date_r = date_limits["max_r"]
    min_date_r = date_limits["min_r"]

    # If user reaches via POST

    if request.method == "GET":
        # Get pickup and return date
        pickupdate = request.args.get("pickupdate")
        returndate = request.args.get("returndate")

        # Redirect if user submits form without complete input
        if not pickupdate or not returndate:
            return redirect("/check")

        # Check if date is valid
        if not is_date(pickupdate) or not is_date(returndate):
            flash("Not a valid date")
            return redirect("/check")

        # If user submits date form check for avaiable cars

        bool_min_p = compare_dates(min_date_p, pickupdate)
        bool_max_p = compare_dates(max_date_p, pickupdate)
        bool_min_r = compare_dates(min_date_r, returndate)
        bool_max_r = compare_dates(max_date_r, returndate)

        # Error checking
        if compare_dates(str(pickupdate), returndate) == 0:
            flash("Returndate must be after pickupdate")
            return redirect("/check")

        elif bool_min_p == 0 or bool_max_p == 1 or bool_min_r == 0 or bool_max_r == 1:
            flash("Incorrect Date!")
            return redirect("/check")

        elif total_Days(pickupdate, returndate) <= 0:
            flash("You must reserve for at least one day")
            return redirect("/check")

        session["pickupdate"] = pickupdate
        session["returndate"] = returndate

        # Check for available dates
        available_cars = db.execute(
            "SELECT * FROM cars WHERE id NOT IN (SELECT car_id FROM active_reservations WHERE (? >= pickupdate AND ? <= returndate) OR (? >= pickupdate AND ? <= returndate) OR (? < pickupdate AND ? > returndate))",
            strdate(pickupdate),
            strdate(pickupdate),
            strdate(returndate),
            strdate(returndate),
            strdate(pickupdate),
            strdate(returndate),
        )

        if len(available_cars) == 0:
            flash("No availble cars for these dates")
            return redirect("/check")

        return render_template("cars.html", cars=available_cars)


@app.route("/reserve", methods=["GET"])
@expire_checkout
def reserve():

    if (
        "pickupdate" not in session
        or "returndate" not in session
        or not session["pickupdate"]
        or not session["returndate"]
    ):
        flash("Select pickup and return date")
        return redirect("/check")

    # Via GET
    if request.method == "GET":

        # If user goes to reserve page without choosing a car redirect to /cars
        car_id = request.args.get("car_id")

        if not car_id:
            return redirect(
                url_for(
                    "cars",
                    pickupdate=session["pickupdate"],
                    returndate=session["returndate"],
                )
            )

        # Get data of selected car
        car = db.execute("SELECT * FROM cars WHERE id = ?", car_id)

        if len(car) == 0:
            flash("INVALID CAR ID")
            return redirect(
                url_for("cars"),
                pickupdate=session["pickupdate"],
                returndate=session["returndate"],
            )

        session["car_id"] = car_id

        c_photos = db.execute("SELECT * FROM photos WHERE car_id = ?", car_id)
        day_price = int(car[0]["day_price"])
        total_days = total_Days(session["pickupdate"], session["returndate"])

        total_price = day_price * total_days
        prepay = 10 * total_days
        left_to_pay = total_price - prepay

        return render_template(
            "reserve.html",
            c_photos=c_photos,
            car=car,
            pickupdate=strdate(session["pickupdate"]),
            returndate=strdate(session["returndate"]),
            total_price=total_price,
            prepay=prepay,
            left_to_pay=left_to_pay,
        )


@app.route("/contact", methods=["GET", "POST"])
@expire_checkout
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
@expire_checkout
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
        return redirect("/check")

    car_id = session["car_id"]

    if "pickupdate" not in session or "returndate" not in session:
        return redirect("/check")

    # Get price of car per day
    day_price = db.execute("SELECT day_price FROM cars WHERE id = ?", car_id)

    if request.method == "POST":

        # Get form fields
        name = request.form.get("fullName")
        pickupdate = session["pickupdate"]
        pickuphour = request.form.get("pickuphour")
        returndate = session["returndate"]
        returnhour = request.form.get("returnhour")

        # Ensure that values are submitet
        if not name or not pickuphour or not returnhour:
            flash("Complete the form!")
            return redirect(url_for("reserve", car_id=car_id))
        elif not session["pickupdate"] or not session["returndate"]:
            flash("Select pickup and return date")
            return redirect("/check")
        # Sql injection check
        elif name.lower() == "null":
            flash("Sorry your name can't be NULL")
            return redirect(url_for("reserve", car_id=car_id))

        # Calculate total days
        total_days = total_Days(pickupdate, returndate)

        # Error checking
        if (
            int(pickuphour) < 6
            or int(pickuphour) > 23
            or int(returnhour) < 6
            or int(returnhour) > 23
        ):
            flash("Car rental is not opened during those hours")
            return redirect(url_for("reserve", car_id=car_id))

        # (Error checking) Check if car is booked

        check = db.execute(
            "SELECT pickupdate, returndate FROM active_reservations WHERE car_id  = ? AND  ((? >= pickupdate AND ? <= returndate) OR (? >= pickupdate AND ? <= returndate) OR (? < pickupdate AND ? > returndate))",
            car_id,
            strdate(pickupdate),
            strdate(pickupdate),
            strdate(returndate),
            strdate(returndate),
            strdate(pickupdate),
            strdate(returndate),
        )
        if len(check) != 0:
            for c in check:
                pdate = strdate_to_d(c["pickupdate"])
                rdate = strdate_to_d(c["returndate"])
                flash(f"Car is not available during {pdate} - {rdate} ! ")
                break

            return redirect("/reserve")

        # Check if car is currently being booked

        check_pending = db.execute(
            "SELECT pickupdate, returndate FROM pending_reservations WHERE car_id  = ? AND  ((? >= pickupdate AND ? <= returndate) OR (? >= pickupdate AND ? <= returndate) OR (? < pickupdate AND ? > returndate))",
            car_id,
            strdate(pickupdate),
            strdate(pickupdate),
            strdate(returndate),
            strdate(returndate),
            strdate(pickupdate),
            strdate(returndate),
        )

        if len(check_pending) != 0:
            flash(
                "Oops someone is currently reserving this car in or between those dates.Check again after 10 minutes or pick other dates."
            )
            return redirect("/reserve")

        # Epoch time
        epoch = int(time.time())

        # Expire time will be 30 minutes after creation(stripe limit is 30 minutes)
        expires = epoch + 30 * 60

        # Get total amount
        total_amount = total_days * day_price[0]["day_price"]

        while True:
            reservation_id = randrange(999999999)
            same_reservation_id = db.execute(
                "SELECT reservation_id FROM active_reservations WHERE reservation_id = ?",
                reservation_id,
            )
            if len(same_reservation_id) == 0:
                break

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
                metadata={"reservation_id": reservation_id},
                expires_at=expires,
                success_url=url_for(
                    "thanks", reservation_id=reservation_id, _external=True
                ),
                cancel_url=url_for("cars", _external=True),
            )

        except Exception as e:
            return str(e)

        # Insert the data in pending booking table
        db.execute(
            "INSERT INTO pending_reservations (name, pickupdate, pickuphour, returndate, returnhour, car_id, total_days, total_price, checkout_id, created) VALUES(?,?,?,?,?,?,?,?,?,?)",
            name,
            strdate(pickupdate),
            pickuphour,
            strdate(returndate),
            returnhour,
            car_id,
            total_days,
            total_amount,
            checkout_session["id"],
            checkout_session["created"],
        )

        return redirect(checkout_session.url, code=303)


@app.route("/thanks", methods=["GET"])
@expire_checkout
def thanks():

    # Get request
    if request.method == "GET":

        # Get reservation id
        reservation_id = request.args.get("reservation_id")
        if not reservation_id:
            flash("NO RESERVATION ID")
            return redirect("/")

        # Get reservation details
        data = db.execute(
            "SELECT * FROM active_reservations WHERE reservation_id = ?", reservation_id
        )
        # Error checking
        if len(data) == 0 or len(data) > 1:
            flash(
                "Something went wrong.If you were redirected here from checkout page after a successful transaction please contact us right now.Else Ignore this message."
            )
            return redirect("/contact")

        # Get car details
        car_id = data[0]["car_id"]
        car_details = db.execute(
            "SELECT car_name, day_price, main_photo_ref FROM cars WHERE id = ? ", car_id
        )
        car_name = car_details[0]["car_name"]
        day_price = int(car_details[0]["day_price"])

        # Amount the person will pay at the dealership
        left_to_pay = (day_price * int(data[0]["total_days"])) - int(data[0]["prepaid"])

        # Reciept url
        receipt_url = db.execute(
            "SELECT receipt_url FROM receipts WHERE payment_intent = ?",
            data[0]["payment_intent"],
        )

        return render_template(
            "thanks.html",
            data=data,
            car_name=car_name,
            left_to_pay=left_to_pay,
            receipt_url=receipt_url[0]["receipt_url"],
            main_photo_ref=car_details[0]["main_photo_ref"],
        )


@app.route("/reservations", methods=["GET"])
@expire_checkout
def reservations():

    if request.method == "GET":
        # Get name and reservation Id
        name = request.args.get("fullname")
        reservation_id = request.args.get("reservation_id")

        if name and reservation_id:

            # Error checking
            if not reservation_id.isnumeric() or len(reservation_id) > 9:
                flash("Not a valid reservation id")
                return redirect("/reservations")
            elif name.lower() == "null":
                flash("Your name can't be null")
                return redirect("/reservations")

            # Check if reservation exists
            check = db.execute(
                "SELECT FROM active_reservations WHERE LOWER(name) = LOWER(?) AND reservation_id = ?",
                name,
                reservation_id,
            )
            if len(check) == 0:
                flash("Reservation doesn't exist")
                return render_template("reservations.html")

            elif len(check) == 1:
                return redirect(url_for("thanks", reservation_id=reservation_id))
            # Error checking: two reservations with same data
            else:
                flash(
                    "Something went wrong. Please contact us if your reservation should be active.Else ignoe this message"
                )
                return redirect("/contact")
        else:
            return render_template("reservations.html")


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
        reservation_id = completed["metadata"]["reservation_id"]

        if completed["payment_status"] != "paid":
            print("NOT PAID")
            return "NOT PAID", 400

        # Get user data from pending_reservations table
        user_data = db.execute(
            "SELECT * FROM pending_reservations WHERE checkout_id = ?", completed["id"]
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
        returnhour = user_data[0]["returnhour"]
        car_id = user_data[0]["car_id"]
        total_days = user_data[0]["total_days"]
        total_price = user_data[0]["total_price"]

        prepaid_warranty = 10 * total_days

        # Insert user data into reservations_history and pending_reservations
        db.execute(
            "INSERT INTO reservations_history (name, email, pickupdate, pickuphour, returndate, returnhour, car_id, total_days, total_price, reservation_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
            name,
            email,
            pickupdate,
            pickuphour,
            returndate,
            returnhour,
            car_id,
            total_days,
            total_price,
            reservation_id,
        )

        db.execute(
            "INSERT INTO active_reservations (name, pickupdate, pickuphour, returndate, returnhour, car_id, total_days, payment_intent, prepaid, phone_number, reservation_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            name,
            pickupdate,
            pickuphour,
            returndate,
            returnhour,
            car_id,
            total_days,
            completed["payment_intent"],
            prepaid_warranty,
            phone_number,
            reservation_id,
        )

        # Delete data in pending_reservations table after transaction completed
        db.execute("DELETE FROM pending_reservations WHERE id = ?", pending_booking_id)

    elif event_dict["type"] == "checkout.session.expired":
        # Delete data in pending_reservations table after sesssion expired
        session_expired = event_dict["data"]["object"]

        db.execute(
            "DELETE FROM pending_reservations WHERE checkout_id = ?",
            session_expired["id"],
        )

        print("checkout session expired")

    elif event_dict["type"] == "charge.succeeded":
        charge = event_dict["data"]["object"]

        # Store receipt url in database

        db.execute(
            "INSERT INTO receipts (payment_intent, receipt_url) VALUES (?,?)",
            charge["payment_intent"],
            charge["receipt_url"],
        )

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
