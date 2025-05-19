# section_calculator.py
# Main application entry point.

from app import create_app

app = create_app()

if __name__ == '__main__':
    # For development, you can run the app like this:
    # The reloader and debugger should be enabled for development.
    # Consider using environment variables for host, port, and debug mode in a real scenario.
    app.run(debug=True, host='0.0.0.0', port=8080)

# Note: For production, a WSGI server like Gunicorn would be used.
# Example Procfile entry: web: gunicorn section_calculator:app
