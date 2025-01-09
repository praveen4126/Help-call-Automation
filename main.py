import csv
import os
import time
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from bs4 import BeautifulSoup
import threading

# Path to your ChromeDriver executable
chromedriver_path = "C:/Users/pravin/Downloads/chromedriver-win64/chromedriver-win64/chromedriver.exe"  # Update the path to your ChromeDriver

# Set Chrome options
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--headless')  # Run in headless mode
chrome_options.add_argument('--ignore-certificate-errors')  # Ignore SSL certificate errors

# Set up the ChromeDriver with options
service = Service(chromedriver_path)
driver = webdriver.Chrome(service=service, options=chrome_options)

# CSV file paths
data_csv = 'data.csv'
form_data_csv = 'form_data.csv'

# Maintain a set of unique rows to prevent duplicates
unique_rows = set()

# Flask application
app = Flask(__name__)

# Function to save rows to CSV
def save_to_csv(headers, rows):
    with open(data_csv, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Write headers only if the file is empty
        if csvfile.tell() == 0:
            writer.writerow(headers)
        writer.writerows(rows)

# Function to fetch and process data from the website
def fetch_data():
    try:
        url = "http://10.244.103.183/ASB2/N_Stop_List/"  # Replace with your URL
        driver.get(url)

        while True:
            try:
                # Locate and interact with dropdown and button
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'DropDownLine')))
                dropdown = Select(driver.find_element(By.ID, 'DropDownLine'))
                dropdown.select_by_value('135')

                WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'View_Btn')))
                generate_button = driver.find_element(By.ID, 'View_Btn')
                generate_button.click()

                # Wait for table to load and scrape data
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'DataGrid1')))
                time.sleep(1)
                html_content = driver.page_source
                soup = BeautifulSoup(html_content, 'html.parser')
                table = soup.find('table', {'id': 'DataGrid1'})

                # Extract table headers and rows
                headers = [header.text.strip() for header in table.find_all('th')]
                new_rows = []
                for row in table.find_all('tr')[1:]:
                    cells = row.find_all('td')
                    row_data = tuple(cell.text.strip() for cell in cells)
                    if row_data and row_data not in unique_rows:
                        unique_rows.add(row_data)
                        new_rows.append(row_data)

                # Save new rows to the CSV
                if new_rows:
                    save_to_csv(headers, new_rows)
                    print(f"New rows added: {new_rows}")
                else:
                    print("No new rows found.")
                time.sleep(1)

            except Exception as e:
                print(f"Error during processing: {e}")
                time.sleep(1)

    except Exception as e:
        print(f"An error occurred in setup: {e}")

    finally:
        driver.quit()

# Function to fetch help call stations
def get_helpcall_stations():
    stations = []
    with open(data_csv, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            stations.append((row[3].strip(), row[4].strip()))
    return stations

# Function to save form data to CSV
def save_form_data_to_csv(data):
    write_headers = not os.path.exists(form_data_csv) or os.path.getsize(form_data_csv) == 0
    with open(form_data_csv, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        if write_headers:
            writer.writerow(['Date', 'Shift', 'Operator Name', 'Raised Time', 'Closed Time', 'Concern Category', 'Problem Description', 'Action Taken'])
        writer.writerow(data)

# Flask routes
@app.route('/', methods=['GET', 'POST'])
def home():
    stations = get_helpcall_stations()
    message = None
    if request.method == 'POST':
        selected_station = eval(request.form['helpcall_alert_station'])
        operator_name = request.form['operator_name']
        problem_description = request.form['problem_description']
        action_taken = request.form['action_taken']

        current_datetime = datetime.now()
        current_date = current_datetime.strftime('%Y/%m/%d')
        closed_time = current_datetime.strftime('%Y/%m/%d %I:%M:%S %p')

        rows, shift, raised_time, row_deleted = [], None, None, False
        with open(data_csv, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader)
            for row in reader:
                station, time_raised = row[3].strip(), row[4].strip()
                if (station, time_raised) == selected_station and not row_deleted:
                    shift, raised_time = row[1], row[4]
                    row_deleted = True
                else:
                    rows.append(row)

        if not row_deleted:
            message = "No matching row found to delete."
        else:
            form_data = [current_date, shift, operator_name, raised_time, closed_time, selected_station[0], problem_description, action_taken]
            save_form_data_to_csv(form_data)
            with open(data_csv, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(header)
                writer.writerows(rows)
            message = "Form submitted successfully and corresponding row deleted from data.csv!"
            
            # Redirect to prevent resubmission on page refresh
            return redirect(url_for('home', message=message))

    return render_template('index.html', stations=stations, message=message)

# Periodic data fetch in a thread
def periodic_fetch_data():
    while True:
        try:
            fetch_data()
        except Exception as e:
            print(f"Error fetching data: {e}")
        time.sleep(7)

if __name__ == "__main__":
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        if not hasattr(app, 'fetch_thread_started'):
            app.fetch_thread_started = True
            fetch_thread = threading.Thread(target=periodic_fetch_data, daemon=True)
            fetch_thread.start()
    app.run(debug=True)
