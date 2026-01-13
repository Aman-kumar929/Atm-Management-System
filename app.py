import os
from flask import Flask, request, session, redirect, render_template,flash
import pymysql
import random
from twilio.rest import Client
from dotenv import load_dotenv


# Load .env file
load_dotenv("private.env")

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")

db = pymysql.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_DATABASE")
)

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_WHATSAPP = os.getenv("TWILIO_WHATSAPP")

client = Client(TWILIO_SID, TWILIO_AUTH)


@app.route("/", methods=["GET","POST"])
def home():
    if request.method == "POST":
        card = request.form["card"]
        session["card"] = card

        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE card_number=%s", (card,))
        user = cur.fetchone()

        if user:
            session["user_id"] = user[0]
            return redirect("/menu")
        
        flash("invalid card number")
        return redirect("/")
    
    return render_template("card.html")



#-------------------------otp portion start------------------------

@app.route("/reset", methods=["GET","POST"])
def reset():
    if request.method == "POST":
        card = request.form["card"]

        cur = db.cursor()
        cur.execute("SELECT phone_number FROM users WHERE card_number=%s", (card,))
        user = cur.fetchone()

        if not user:
            flash("invalid , please check detail")
            return redirect("/reset")

        phone_number = user[0]
        otp = str(random.randint(100000,999999))
 
        #store otp in session
        session["otp"] = otp
        session["otp_card"] = card 

        #send whatsapp otp
        client.messages.create(
            body = f"your atm card pin reset otp is {otp}",
            from_ = TWILIO_WHATSAPP,
            to = f"whatsapp:{phone_number}"
        )

        return redirect("/verify_otp")
    return render_template("reset.html")


@app.route("/verify_otp", methods=["GET","POST"])
def verify_otp():
    if request.method == "POST":
        user_otp = request.form["otp"]

        if user_otp == session.get("otp"):
            return redirect("/reset_pin")
        
        flash("invalid otp", "otp")
        return redirect("/verify_otp")
    
    return render_template("otp.html")


@app.route("/reset_pin", methods=["GET","POST"])
def reset_pin():
    if request.method == "POST":
        new_pin = request.form["pin"]
        card = session.get("otp_card")

        cur = db.cursor()
        cur.execute("UPDATE users SET pin=%s WHERE card_number=%s", (new_pin,card))
        db.commit()

        session.pop("otp", None)
        session.pop("otp_card", None)

        return redirect("/")
    return render_template("/reset_pin.html")

#----------------------------otp portion end----------------------------


@app.route("/menu", methods=["GET","POST"])
def menu():
    if "user_id" not in session:
        return redirect("/")
    
    if request.method == "POST":
        choice = request.form["choice"]

        if choice == "balance":
            return redirect("/check_balance")
        elif choice == "withdraw":
            return redirect("/withdraw")

    return render_template("menu.html")  


@app.route("/check_balance", methods=["GET", "POST"])
def check_balance():
    if request.method == "POST":
        pin = request.form["pin"]

        cur = db.cursor()
        cur.execute("SELECT savings_balance , current_balance FROM users WHERE id=%s AND pin=%s", (session["user_id"],pin))
        user = cur.fetchone()
        
        if not user:
            flash("invalid pin")
            return redirect("/check_balance")
        
        session["savings_balance"] = user[0]
        session["current_balance"] = user[1]
        
        return redirect("/show_balance")

    return render_template("check_balance.html") 


@app.route("/show_balance")
def show_balance():
    return render_template("show_balance.html")


@app.route("/withdraw", methods=["GET","POST"])
def withdraw():
    if request.method == "POST":
        account = request.form["account"]
        session["account"] = account
        return redirect("/withdraw_cash")
    
    return render_template("withdraw.html")


@app.route("/withdraw_cash", methods=["GET","POST"])
def withdraw_cash():
    if request.method == "POST":
        amount = int(request.form["amount"])
        pin = request.form["pin"]
        account = session.get("account")

        if amount % 500 != 0:
            flash("invalid , only in 500 series", "amount")
            return redirect("/withdraw_cash")
        
        cur = db.cursor()
        cur.execute("SELECT savings_balance , current_balance FROM users WHERE id=%s AND pin=%s", (session["user_id"],pin))
        user = cur.fetchone()
        
        if not user:
            flash("invalid pin", "pin")
            return redirect("/withdraw_cash")
        
        savings,current = user

        if account == "savings":
            if savings < amount:
                flash("insufficient savings balance", "balance")
                return redirect("/withdraw_cash")
            
            cur.execute("UPDATE users SET savings_balance = savings_balance - %s WHERE id=%s", (amount,session["user_id"]))
            
        elif account == "current":
            if current < amount:
                flash("insufficient current balance", "balance")
                return redirect("/withdraw_cash")
            
            cur.execute("UPDATE users SET current_balance = current_balance - %s WHERE id=%s", (amount,session["user_id"]))

        db.commit()
        session.pop("account", None)
         
        flash(f"collect your amount: {amount}", "collect")
        return redirect("/withdraw_cash")
    
    return render_template("withdraw_case.html")


if __name__ == "__main__":
    # app.run(debug=True)
    app.run(host="0.0.0.0",port=5000,debug=True)    # to test in mobile use this 
    