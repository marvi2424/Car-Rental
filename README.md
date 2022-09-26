# Car Rental
#### Video Demo:  https://youtu.be/Vh97PE-NZ5U
#### Description:

My project is a flask application which handles car rental bookings, displays cars of the business and much more. It was made with
flask, sqlite, html, css, jinja, and bootstrap.

For this project i wrote multiple files
Three files can be considered the backend. Those files are app.y, helpers.py and store.py.
In the file app.py is where all the backend of the application is taking place. It handles everything from routes, databases, storing data, receving date and more importantly checking data. Espencially the dates. I say espencially because I had to mak esure that the user doesn't corrupt dates. For example he can chooce a date in the past and "book" the car in the past or in the distant future. But I only allowed booking within a month of time not more. Also I made sure that the pickupdate would be before releasedate otherwise the total days of booking would be a negative number.
In the file helpers.py like the name suggests where are helper functions which are used in the main file app.py.
In the file store.py is where i store the data in the database. I get the admin input, store it in variables and then use a sql query to store it in the respective table in the sqlite rental database. There are different function like store car data, car photos of frequently asked questions.

In this project there are 5 routes  in total : index, cars, book, contact and faq.
In index there is information about the business and why this business is the best and why people should book our cars.There is a carousel of very cool and professional photos on top and each of them contains a heading and some text which can be about the business. Below there are the best qualitites of the business
like speed and ease, comfort, security etc. Above each there is a cool rounded png to make it more aesthetically pleasing. Below there are some featurettes with some placeholding text.

In the  cars route, all the available vehicles are displayed and with some information about them.For example the name of the car, number of persons it can hold, color, transmission, parkig sensor, fuel type, tank capacity etc. To be more precie the cars that are shown are the cars  which are not booked in any dates. If the user completes the form (which is on top of the page) to check for available cars more cars may appear.Those cars who appear are not booked on the dates submitet in the form.

In book page is where the user does the booking of the car. If the car is booked there will be displayed in which cars are booked for example 02/02/2022- 02/03/2022.To book the car the user has to complete the form (name, email, pickuphour, pickupdate, releasedate and releasehour), If he chooses the period in which car is booked he will be redirected to the same page but with a message on top which says: Car is booked during mm/dd/yyyy - mm/dd/yyyy. This page was the hardest to make.

In contact, contact information is displayed. Also there is a form which the user can complete and write a message.The user has to submit name, email, phone number and a message. All this data will be stored in the sqlite database.

In faq page, well the are FAQs. All the FAQs are also stored in the sqlite database

In the style.css is where the stying of the webpages takes place and in form-validation.js is where forms are validates. It just makes sure that the users input complete information in the required fields. There are also 2 folders c_phtos and photos which store photos of the web pages and phtos of the cars.




