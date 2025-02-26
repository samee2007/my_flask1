from flask import Flask, render_template, request, redirect, url_for, flash,session
import mysql.connector
from datetime import datetime ,timedelta
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from flask import Response
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:  # Check if the user is logged in
            flash('You need to log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

db_config = {
    'host': 'localhost',
    'user': 'root',           
    'password': '',           
    'database': 'calorie_tracker' 
}

def get_meals():
    """Fetch meals from the last 2 days"""
    conn = mysql.connector.connect(
        host="localhost",
        user="root",  # Change if you set a different user
        password="",  # Change if you set a password
        database="calorie_tracker"
    )
    cursor = conn.cursor(dictionary=True)  # Returns data as a dictionary

    two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    cursor.execute("SELECT food_item, quantity, meal_type, date FROM Meals WHERE date >= %s ORDER BY date DESC", (two_days_ago,))
    
    meals = cursor.fetchall()
    conn.close()
    return meals

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
@app.route("/")
@app.route("/login",methods=["POST","GET"])
def login():
    conn=0
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM Users WHERE email = %s AND password_hash = %s", (email, password))
            user = cursor.fetchone()

            if user: 
                user_id = user[0]
                username = user[1]  
                session['user_id'] = user_id
                return redirect(url_for('dashboard', username=username))
            else:
                flash('Invalid email or password. Please try again.', 'danger')


        except mysql.connector.Error as err:
            return f"Error: {err}", 500
        finally:
            if conn:
                conn.close()
    return render_template('login.html')

@app.route('/users', methods=['GET', 'POST'])
def users():
    return render_template('users.html')

@app.route('/create_account', methods=['POST'])
def create_account():
    conn=None
    username = request.form['username']
    gender = request.form['gender']
    age = request.form['age']
    email = request.form['email']
    password = request.form['password']
    height_cm = request.form['height_cm']
    weight_kg = request.form['weight_kg']
    activity_level = request.form['activity_level']
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        query = """
                INSERT INTO users (username, gender, age, email, password_hash, height, weight, activity_level)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
        cursor.execute(query, (username, gender, age, email, password, height_cm, weight_kg, activity_level))
        conn.commit()
        user_id = cursor.lastrowid

        session['user_id'] = user_id
        session['username'] = username

        flash('Account created successfully!', 'success')
        return redirect(url_for('dashboard'))

    except mysql.connector.Error as err:
            flash(f"Error: {err}", 'danger')
    finally:
            if conn is not None and conn.is_connected():
                cursor.close()
                conn.close()
    return redirect(url_for('users')) 
   

@app.route('/dashboard')
@login_required
def dashboard():
   if 'user_id' not in session:
        flash('You need to log in first.', 'danger')
        return redirect(url_for('login'))
   username = session.get('username','user')
   return render_template('dashboard.html',username=username)

@app.route('/calorie-measurement', methods=['GET', 'POST'])
@login_required
def calorie_measurement():
    conn = None
    food_items = [] 
    total_calories = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = "SELECT food_name FROM fooddatabase"
        cursor.execute(query)
        food_items = [row[0] for row in cursor.fetchall()]

    except mysql.connector.Error as err:
        flash(f"Database Error: {err}", 'danger')
    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

    if request.method == 'POST':
        food_item = request.form.get('food_item')
        quantity = int(request.form.get('quantity'))
        total_calories = 0
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("SELECT calories_per_serving FROM fooddatabase WHERE food_name = %s", (food_item,))
            result = cursor.fetchone()

            if result:  
                food = result[0]
                total_calories = food * quantity
            else:
                flash(f"Food item '{food_item}' not found in the database.", 'warning')
            
        except mysql.connector.Error as err:
            flash(f"Database Error: {err}", 'danger')
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

    return render_template('calorie_measurement.html', food_items=food_items,total_calories=total_calories)   

@app.route('/food-suggestion', methods=['get'])
@login_required
def food_suggestion():
    return render_template('food_suggestion.html')

@app.route('/get_suggestion', methods=['POST'])
@login_required
def get_suggestion():
    conn=None
    try:  
        remaining_calories = int(request.form['remaining_calories'])
        dietary_preference = request.form['dietary_preference']
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        if dietary_preference == "none":
            query = """
                    SELECT food_name, calories_per_serving, serving_size,dietary_preference
                    FROM fooddatabase 
                    WHERE calories_per_serving <= %s
                """
            cursor.execute(query, (remaining_calories,))
        else:
            query = """
                    SELECT food_name, calories_per_serving, serving_size,dietary_preference
                    FROM fooddatabase 
                    WHERE calories_per_serving <= %s AND dietary_preference = %s
                """
            cursor.execute(query, (remaining_calories, dietary_preference))
        food_suggestions = cursor.fetchall()
        if food_suggestions:
                return render_template('food_suggestions_result.html', food_suggestions=food_suggestions)
        else:
                return "No food suggestions found for the given criteria.", 404

    except mysql.connector.Error as err:
            print(f"Error: {err}")
    finally:
            if conn is not None and conn.is_connected():
                cursor.close()
                conn.close()

@app.route('/calorie-target', methods=['GET', 'POST'])
@login_required
def calorie_target():

    if "user_id" not in session:
        return redirect(url_for('login'))  
    conn = None
    user_id = session['user_id'] 
    daily_goal = None
    weekly_goal = None
    monthly_goal = None
    existing_goal = None
    if request.method == 'POST':
        daily_goal = int(request.form.get('daily_goal'))
        weekly_goal = daily_goal * 7
        monthly_goal = daily_goal*30

        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM caloriegoals WHERE user_id = %s", (user_id,))
            existing_goal = cursor.fetchone()

            if existing_goal:
                query = """
                    UPDATE caloriegoals
                    SET daily_goal = %s, weekly_goal = %s, monthly_goal = %s, last_updated = NOW()
                    WHERE user_id = %s
                """
                cursor.execute(query, (daily_goal, weekly_goal, monthly_goal, user_id))
                flash('Calorie target updated successfully!', 'success')
            else:
                query = """
                    INSERT INTO caloriegoals (user_id, daily_goal, weekly_goal, monthly_goal, last_updated)
                    VALUES (%s, %s, %s, %s, NOW())
                """
                cursor.execute(query, (user_id, daily_goal, weekly_goal, monthly_goal))
                flash('Calorie target created successfully!', 'success')
            conn.commit()
            
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", 'danger')
        finally:
            if conn:
                cursor.close()
                conn.close()
    if request.method == 'GET':
            try:
                conn = mysql.connector.connect(**db_config)
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM caloriegoals WHERE user_id = %s", (user_id,))
                existing_goal = cursor.fetchone()
                if existing_goal:
                    daily_goal = existing_goal['daily_goal']
                    weekly_goal = existing_goal['weekly_goal']
                    monthly_goal = existing_goal['monthly_goal']
            except mysql.connector.Error as err:
                    flash(f"Database error: {err}", 'danger')
            finally:
                 if conn:
                   cursor.close()
                   conn.close()

    return render_template('calorie_target.html', daily_goal=daily_goal, 
        weekly_goal=weekly_goal, 
        monthly_goal=monthly_goal)

@app.route('/enter_meal', methods=['GET', 'POST'])
@login_required
def enter_meal():
    if 'user_id' not in session:  
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn=None
    food_items= []
    meals=[]

    try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            query = "SELECT food_name FROM fooddatabase"
            cursor.execute(query)
            food_items= [row["food_name"] for row in cursor.fetchall()]

            cursor.execute("""
                SELECT meal_id,user_id, food_item, quantity, meal_type, calories, logged_at
                FROM meals
                WHERE user_id = %s AND logged_at >= NOW() - INTERVAL 2 DAY
                ORDER BY logged_at DESC
            """, (user_id,))
            meals = cursor.fetchall()

    except mysql.connector.Error as err:
        flash(f"Database Error: {err}", 'danger')
    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()    

    if request.method == 'POST':
        food_item = request.form.get('food_item')
        quantity = int(request.form.get('quantity'))
        meal_type = request.form.get('meal_type')
        
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()

            query = "SELECT calories_per_serving FROM fooddatabase WHERE food_name = %s"
            cursor.execute(query, (food_item,))
            result = cursor.fetchone()
            if result:
                calories_per_unit = result[0]
            else:
                flash("Invalid food item selected.", "danger")
                return redirect(url_for('enter_meal'))
            # Calculate total calories
            total_calories = calories_per_unit * quantity

            # Insert the meal into the meals table
            query = """
                INSERT INTO meals (user_id, food_item, quantity, meal_type, calories, logged_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """
            cursor.execute(query, (user_id, food_item, quantity, meal_type, total_calories))  # Replace `1` with dynamic user_id
            conn.commit()

            flash('Meal added successfully!', 'success')
        except mysql.connector.Error as err:
            flash(f"Database Error: {err}", 'danger')
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

        return redirect(url_for('enter_meal'))
    return render_template('enter_meal.html', food_items=food_items,meals=meals)

@app.route('/edit_meal/<int:meal_id>', methods=['GET', 'POST'])
@login_required
def edit_meal(meal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = None
    meal = None
    food_items = []

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Fetch meal details
        cursor.execute("SELECT * FROM meals WHERE meal_id = %s", (meal_id,))
        meal = cursor.fetchone()

        # Fetch food items
        cursor.execute("SELECT food_name FROM fooddatabase")
        food_items = [row['food_name'] for row in cursor.fetchall()]

    except mysql.connector.Error as err:
        flash(f"Database Error: {err}", 'danger')
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    if not meal:
        flash("Meal not found!", "danger")
        return redirect(url_for('enter_meal'))

    if request.method == 'POST':
        food_item = request.form.get('food_item')
        quantity = int(request.form.get('quantity'))
        meal_type = request.form.get('meal_type')

        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()

            cursor.execute("SELECT calories_per_serving FROM fooddatabase WHERE food_name = %s", (food_item,))
            calories_per_unit = cursor.fetchone()[0]

            total_calories = calories_per_unit * quantity

            cursor.execute("""
                UPDATE meals
                SET food_item = %s, quantity = %s, meal_type = %s, calories = %s, logged_at = NOW()
                WHERE meal_id = %s AND user_id = %s
            """, (food_item, quantity, meal_type, total_calories, meal_id, session['user_id']))
            conn.commit()

            flash("Meal updated successfully!", "success")
            return redirect(url_for('enter_meal'))

        except mysql.connector.Error as err:
            flash(f"Database Error: {err}", 'danger')
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

    return render_template('edit_meal.html', meal=meal, food_items=food_items)

@app.route('/delete_meal/<int:meal_id>', methods=['POST'])
@login_required
def delete_meal(meal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM meals WHERE meal_id = %s AND user_id = %s", (meal_id, session['user_id']))
        conn.commit()

        flash("Meal deleted successfully!", "success")
    except mysql.connector.Error as err:
        flash(f"Database Error: {err}", 'danger')
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    return redirect(url_for('enter_meal'))

@app.route('/view-calorie-chart', methods=["GET", "POST"])
@login_required
def view_calorie_chart():
    if 'user_id' not in session:  
        return redirect(url_for('login'))

    user_id = session['user_id']  

    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT daily_goal, weekly_goal, monthly_goal FROM caloriegoals WHERE user_id = %s", (user_id,))
        calorie_goals = cursor.fetchone()

        if not calorie_goals:
            flash("No calorie target found. Please set a calorie target first.", 'warning')
            return redirect(url_for('calorie_target'))

        if request.method == "POST":
            chart_type = request.form.get("chart_type")  # Get user selection

            # Fetch user's logged meals
            cursor.execute("""
                SELECT 
                    DATE(logged_at) AS log_date,
                    SUM(calories) AS total_calories
                FROM meals
                WHERE user_id = %s
                GROUP BY DATE(logged_at)
            """, (user_id,))
            daily_data = cursor.fetchall()

            daily_df = pd.DataFrame(daily_data)
            if daily_df.empty:
                flash("No meals logged. Please enter your meals to view the chart.", 'warning')
                return redirect(url_for('enter_meal'))

            daily_df['log_date'] = pd.to_datetime(daily_df['log_date'])

            today = pd.Timestamp.now().normalize()

            if chart_type == "daily":
                achieved = daily_df[daily_df['log_date'] == today]['total_calories'].sum()
                target = calorie_goals['daily_goal']
                title = "Daily Calorie Chart"

            elif chart_type == "weekly":
                seven_days_ago = today - pd.Timedelta(days=7)
                achieved = daily_df[daily_df['log_date'] >= seven_days_ago]['total_calories'].sum()
                target = calorie_goals['weekly_goal']
                title = "Weekly Calorie Chart"

            elif chart_type == "monthly":
                thirty_days_ago = today - pd.Timedelta(days=30)
                achieved = daily_df[daily_df['log_date'] >= thirty_days_ago]['total_calories'].sum()
                target = calorie_goals['monthly_goal']
                title = "Monthly Calorie Chart"

            else:
                flash("Invalid selection. Please choose a valid option.", 'danger')
                return redirect(url_for('view_calorie_chart'))

            # Generate the bar chart
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.bar(["Target"], [target], width=0.4, label='Target', color='blue')
            ax.bar(["Achieved"], [achieved], width=0.4, label='Achieved', color='green')

            ax.set_ylabel('Calories')
            ax.set_title(title)  # Display the selected chart type
            ax.legend()

            # Save the chart
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close()

            return Response(buf, mimetype='image/png')

        return render_template("select_chart.html")  # Load selection page

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'danger')
        return redirect(url_for('dashboard'))
    finally:
        if conn:
            cursor.close()
            conn.close()

@app.route('/logout')
def logout():
    session.clear()  # Clear all session data
    return redirect(url_for('login'))  # Redirect to the login page




if __name__ == '__main__':
    app.run(debug=True)
