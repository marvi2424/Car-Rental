# Store data in sqlite database

from cs50 import SQL

# Configure CS50 library to use Sqlite database
db = SQL("sqlite:///rental.db")

# Store car data


def store_car_data():
    car_name = input("Car name: ")
    transmission = input("Transmission: ")
    seats = input("Seats: ")
    fuel_type = input("Fuel_type: ")
    fuel_capacity = input("Fuel_capacity: ")
    main_photo_ref = input("Main photo ref: ")
    day_price = input("Price per day: ")
    color = input("Color:")
    p_sensor = input("Parking sensor: ")

    db.execute("INSERT INTO cars (car_name, transmission, seats, fuel_type, fuel_capacity, main_photo_ref, day_price, color, parking_sensor) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
               car_name, transmission, seats, fuel_type, fuel_capacity, main_photo_ref, day_price, color, p_sensor)

# Store car photos


def store_car_photos():
    car_id = input("Car id: ")
    photo_ref = '/static/c_photos/' + input("Photo ref: ")
    db.execute("INSERT INTO photos (car_id, photo_ref) VALUES (?,?)", car_id, photo_ref)


# Store faq


def store_faq():
    section = input("Section: ")
    question = input("Question: ")
    answer = input("Answer: ")

    db.execute("INSERT INTO faq (section, question, answer) VALUES (? ,?, ?)", section, question, answer)

# Main


def main():

    answer = input("Do you want to store (1) car photos or (2)car data or (3) FAQ? Type 1 or 2 or 3: ")

    if int(answer) == 2:
        store_car_data()
    elif int(answer) == 1:
        store_car_photos()
    elif int(answer) == 3:
        store_faq()
    else:
        print("Try again")


main()
