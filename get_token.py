"""
Ovo se pokrene jedanput samo da se dobije token
"""
import http.server
import urllib.parse
import webbrowser
import requests
import json
import sys

CLIENT_ID = "clientid"
CLIENT_SECRET = "clientsecret"
REDIRECT_URI = "http://172.0.0.1:8888/callback" # obavezno dodat u spotify panel
SCOPE = "user-read-currently-playing user-read-playback-state"

auth_url = (
    "https://accounts.spotify.com/authorize?"
    + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": SCOPE,
        "redirect_uri": REDIRECT_URI,
    })
)

authorization_code = None

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global authorization_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            authorization_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Success! You can close this tab.</h1>")
        elif "error" in params:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<h1>Error: {params['error'][0]}</h1>".encode())
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass

print("Opening browser for Spotify authorization...")
webbrowser.open(auth_url)

server = http.server.HTTPServer(("localhost", 8888), CallbackHandler)
print("Waiting for callback on http://localhost:8888/callback ...")
server.handle_request() 
server.server_close()

if not authorization_code:
    print("ERROR: No authorization code received.")
    sys.exit(1)

print(f"Got authorization code, exchanging for tokens...")

token_response = requests.post(
    "https://accounts.spotify.com/api/token",
    data={
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": REDIRECT_URI,
    },
    auth=(CLIENT_ID, CLIENT_SECRET),
)

if token_response.status_code != 200:
    print(f"ERROR: Token exchange failed: {token_response.text}")
    sys.exit(1)

tokens = token_response.json()
print("\n" + "=" * 60)
print("SUCCESS! Save these values:\n")
print(f"  ACCESS_TOKEN  = {tokens['access_token'][:20]}... (expires in {tokens['expires_in']}s)")
print(f"  REFRESH_TOKEN = {tokens['refresh_token']}")
print(f"\nPut the REFRESH_TOKEN in your .env file.")
print("=" * 60)

with open("tokens.json", "w") as f:
    json.dump(tokens, f, indent=2)
    print(f"\nFull tokens also saved to tokens.json")