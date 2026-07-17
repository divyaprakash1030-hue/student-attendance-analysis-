from flask import Flask, render_template, request
import pandas as pd
import os
import traceback

app = Flask(__name__)

# VERCEL COMPATIBLE PATH: This ensures the app finds the CSV on the cloud server
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILENAME = os.path.join(BASE_DIR, 'large_attendance.csv')

def get_student_analytics(s_id, s_name):
    """
    Reads the CSV, cleans it, and generates overall and subject-wise stats.
    """
    try:
        if not os.path.exists(FILENAME):
            return "error_missing", f"File '{FILENAME}' not found. Please ensure it is uploaded."

        # Read CSV: We read only the first 6 columns to prevent "Expected 6 saw 7" errors
        # on_bad_lines='skip' is an extra safety measure
        df = pd.read_csv(FILENAME, usecols=[0,1,2,3,4,5], on_bad_lines='skip', skipinitialspace=True)
        
        # Clean Headers: Strip any invisible spaces
        df.columns = df.columns.str.strip()
        
        # Standardize Data: Strip spaces from IDs and Names
        df['Name'] = df['Name'].astype(str).str.strip()
        df['StudentID'] = df['StudentID'].astype(str).str.strip()
        df['Status'] = df['Status'].astype(str).str.strip()
        
        # Safeguard: Ensure 'leave_reason' column exists for the HTML
        # Even if we only read 6 columns, we create this for the template logic
        if 'leave_reason' not in df.columns:
            df['leave_reason'] = "Medical Issue" # Default reason

        # Filter: Case-insensitive name match and exact ID match
        user_data = df[(df['StudentID'] == str(s_id)) & 
                       (df['Name'].str.lower() == s_name.lower())]
        
        if user_data.empty:
            return "not_found", "No records found. Please check your ID and Name."

        # --- CALCULATIONS ---
        total = len(user_data)
        present = len(user_data[user_data['Status'] == 'Present'])
        absent = len(user_data[user_data['Status'] == 'Absent'])
        percent = round((present / total) * 100, 1)

        # Subject-Wise Analysis
        # Grouping by Subject to get individual performance
        sub_group = user_data.groupby('Subject')['Status'].value_counts().unstack().fillna(0)
        
        # Ensure columns exist to avoid KeyError
        if 'Present' not in sub_group: sub_group['Present'] = 0
        if 'Absent' not in sub_group: sub_group['Absent'] = 0
        
        subject_data = []
        for sub, row in sub_group.iterrows():
            sub_total = row['Present'] + row['Absent']
            sub_per = round((row['Present'] / sub_total) * 100, 1)
            subject_data.append({
                'subject': sub,
                'percent': sub_per
            })

        summary = {
            'name': user_data.iloc[0]['Name'].upper(),
            'id': s_id,
            'total': total,
            'present': present,
            'absent': absent,
            'percent': percent,
            'eligibility': "ELIGIBLE FOR EXAMS" if percent >= 75 else "SHORTAGE OF ATTENDANCE",
            'theme_color': "#198754" if percent >= 75 else "#dc3545",
            'subject_data': subject_data
        }

        return "success", {"summary": summary, "records": user_data.to_dict(orient='records')}

    except Exception as e:
        # Prints the full error log to the Vercel/Local terminal for debugging
        traceback.print_exc()
        return "error", str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_attendance', methods=['POST'])
def check_attendance():
    # Retrieve form data and strip accidental spaces
    s_id = request.form.get('student_id', '').strip()
    s_name = request.form.get('name', '').strip()
    
    status, result = get_student_analytics(s_id, s_name)
    
    if status == "success":
        return render_template('result.html', 
                               summary=result['summary'], 
                               records=result['records'])
    else:
        # Pass the error message back to the home screen
        return render_template('index.html', error=result)

# For Vercel, the app must be global. The below block is for local testing.
if __name__ == '__main__':
    app.run(debug=True)