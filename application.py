import os

import sqlite3
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = sqlite3.connect("finance.db", check_same_thread=False)
crsr = db.cursor() 

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # if came via post
    if request.method == "POST":

        # if any of the info is not filled by the user then apologize
        if not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            return apology("Please enter username and password")


        # if both the passwords doesn't match then apologize
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Your passwords doesn't match")

        username = request.form.get("username")
        all_usernames = crsr.execute('SELECT count(*) FROM users WHERE username = :username', {"username": username}).fetchone()[0]
        if all_usernames != 0:
            return apology("username already in use")

        # encrypting the password
        hashpass = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)

        # Noting the user's info
        insertion = crsr.execute('INSERT INTO "users"("username","hash") VALUES(:a, :b)', {'a':request.form.get("username"), 'b':hashpass})
        db.commit()

        # if insertion in database not possible then apologize
        if not insertion:
            return apology("username already in use")

        # return to the login page
        return redirect("/login")
    if request.method == "GET":
        return render_template("/register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = crsr.execute("SELECT count(*), id, username, hash FROM users WHERE username = :username",
                          {"username": request.form.get("username")}).fetchall()[0]
        print("I m printing ", rows)
        print(dir(rows))
        # Ensure username exists and password is correct
        if rows[0] != 1 or not check_password_hash(rows[3], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[1]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # get the purchased and sold symbol and their shares
    purshares = crsr.execute(
        "SELECT symbol, SUM(shares) as share FROM purchase_list WHERE user_id= :user GROUP BY symbol", {"user": session["user_id"]}).fetchall()
    print(purshares)
    soldshares = crsr.execute(
        "SELECT symbol, SUM(shares) as share FROM sell_list WHERE user_id= :user GROUP BY symbol", {"user":session["user_id"]}).fetchall()
    print(soldshares)
    usercash = crsr.execute("SELECT cash FROM users WHERE id = :userid", {"userid": session["user_id"]}).fetchall()[0]
    print(usercash)
    
    
    total = usercash[0]
    # if nothing shows up then show the page with nothing to show
    if not purshares and not soldshares:
        return render_template("/index.html", nothing="nothing to show to you", cash=usercash[0], total=total)
    finalshares = []
    entry = {}
    total = usercash[0]
    # add the current price of the share
    for i in range(len(purshares)):
        entry["symbol"] = purshares[i][0]
        entry["share"] = purshares[i][1]
        for j in range(len(soldshares)):
            if soldshares[j][0] == purshares[i][0]:
                entry["share"] = purshares[i][1] - soldshares[j][1]
        if entry["share"] == 0:
            continue
        quote = lookup(entry["symbol"])
        entry["price"] = quote["price"]
        entry["amount"] = entry["share"] * quote["price"]
        total += entry["amount"]
        finalshares.append(entry.copy())
    if not finalshares:
        return render_template("/index.html", nothing="nothing to show to you", cash=usercash[0], total=total)

    # show the magic
    return render_template("/index.html", forms=finalshares, cash=usercash[0], total=total)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = crsr.execute("""SELECT "BOUGHT" as action, symbol, shares, price, time FROM purchase_list WHERE user_id= :user
                          UNION
                          SELECT "SOLD" as action, symbol, shares, price, time FROM sell_list WHERE user_id= :user""", {"user":session["user_id"]}).fetchall()
    final_history = []
    for i in history:
        final_history.append({"action": i[0], "symbol": i[1], "shares": i[2], "price": i[3], "time": i[4]})

    return render_template("history.html", stocks=final_history)


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # if the user didn't enter the stock symbol
        if not request.form.get("symbol") or not request.form.get("symbol").isalpha():
            return apology("Enter valid symbol")

        # check the current price of the stock if the symbol exists and show it
        quoted = lookup(request.form.get("symbol"))
        print(quoted)
        if not quoted:
            return apology("Wrong symbol")

        return render_template("/quoted.html", info=quoted)
    return render_template("/quote.html")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        # if symbol or the no of shares are not entered
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("Enter symbol and the number of shares")

        # if the entered company doesn't exist
        elif not quote:
            return apology("There exists no company with that symbol")

        # take shares, the amount of those shares and the userinfo
        shares = request.form.get("shares")
        if not shares.isdigit():
            return apology("Enter the number of shares correctly")
        shares = float(shares)
        amount = shares * float(quote['price'])
        userinfo = crsr.execute("SELECT * FROM users WHERE id = :userid", {"userid":session["user_id"]}).fetchall()[0]

        # if entered shares are negative
        if shares < 0:
            return apology("Enter the number of shares in positive quantity")

        # if the cash user have is less than the amount of shares
        elif float(userinfo[-1]) < amount:
            return apology("You have low money")

        # if everything is alright

        # reduce the amount of cash in user account
        crsr.execute('UPDATE "users" SET "cash" = :cash WHERE "id" = :userid',
                   {"cash":float(userinfo[-1]) - amount, "userid":session["user_id"]})
        # note down the purchase
        crsr.execute('INSERT INTO purchase_list("symbol", "user_id", "shares", "price") VALUES(:symbol, :userid, :shares, :price)',
                   {"symbol":request.form.get("symbol"), "userid":session["user_id"], "shares":shares, "price":amount})
        db.commit()
        return redirect("/")
    return render_template("buy.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # if came to the page via POST
    if request.method == "POST":

        # if user didn't enter symbol or the shares then apologize
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("Enter the symbol and the number of shares")

        # get the symbol and the number of shares
        symbol = request.form.get("symbol")
        print("The fucking symbol is: ", symbol)
        shares = int(request.form.get("shares"))
        print("The fucking number of shares is: ", shares)

        # getting the user's transaction's info
        pur_stocks = crsr.execute('SELECT * FROM purchase_list WHERE user_id= :user and symbol= :sym',
                                {"user": session["user_id"], "sym":symbol}).fetchall()
        sell_stocks = crsr.execute('SELECT count(*), * FROM sell_list WHERE user_id= :user and symbol= :sym',
                                 {"user": session["user_id"], "sym":symbol}).fetchall()
        totalsharesavail = 0
        print("The fucking pur_stocks is: ", pur_stocks)
        print("The fucking sell_stocks is: ", sell_stocks)


        # finding the total number of available shares of the user of the selected symbol

        for i in pur_stocks:
            totalsharesavail += int(i[3])
        if sell_stocks[0][0] != 0:
            for i in sell_stocks:
                totalsharesavail -= int(i[4])

        # if user doesn't have enough number of shares then apologize
        if totalsharesavail < shares:
            return apology("You have less shares of that company")

        # Updating the new amount of cash the user have
        user = crsr.execute('SELECT * FROM users WHERE id= :user', {"user":session["user_id"]}).fetchone()
        stock = lookup(symbol)
        print("The fucking user is: ", user)
        print("The fucking stock is: ", stock)
        newamountleft = user[3] + shares * stock["price"]
        crsr.execute("UPDATE users SET cash= :newcash WHERE id= :user",
                   {"newcash":newamountleft, "user":session["user_id"]})

        # Noting the sell transaction
        crsr.execute('INSERT INTO sell_list("symbol", "user_id", "shares", "price") VALUES(:symbol, :userid, :shares, :price)',
                   {"symbol": symbol, "userid": session["user_id"], "shares": shares, "price": shares * stock["price"]})
        db.commit()

        # go to the homepage
        return redirect("/")
    stocks = crsr.execute('SELECT * FROM purchase_list WHERE user_id= :user', {"user": session["user_id"]}).fetchall()
    final_stock = []
    for i in stocks:
        final_stock.append({"symbol": i[1]})
    return render_template("/sell.html", stocks=final_stock)


@app.route("/chpass", methods=["POST", "GET"])
@login_required
def chpass():
    if request.method == "POST":
        if not request.form.get("currentpass") or not request.form.get("newpass"):
            return apology("Enter both the passwords")

        rows = crsr.execute("SELECT * FROM users WHERE id = :userid",
                          {"userid":session["user_id"]}).fetchone()
        print(rows)
        # Ensure username exists and password is correct
        if not check_password_hash(rows[2], request.form.get("currentpass")):
            return apology("You have entered wrong current password")

        hashpass = generate_password_hash(request.form.get("newpass"), method='pbkdf2:sha256', salt_length=8)
        crsr.execute("UPDATE users SET hash = :passw WHERE id= :user", {"passw":hashpass, "user":session["user_id"]})
        db.commit()
        return redirect("/")

    return render_template("/changepass.html")