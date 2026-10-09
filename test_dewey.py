import os

api_key = os.getenv("DEWEY_API_KEY")

if api_key:
    print("Dewey API key loaded successfully.")
else:
    print("No API key found.")