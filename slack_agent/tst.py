import requests

access_token = "AQVyHb_LUDQjvAPtIaJJoO-q5BxW7NL9C5Zyvai6slnb5n8A73R5MHHWkeTemZKRb4F4WpcjTcLp1xjsDUGFtyO80y9o4cchYrZbPcQYKX8S-0OEg8bL-m4fqvbdnZLyIEMQxDf1THufxe9UQ-jiZ1Q8h8OMez98JV6zJS4zPMSPTWYhA_7VH_fTL8XtYoMZAdzZH8EKPSX0cMnGYdkYvoMoSgDLrxI5g7vJUpeQj4kP7L6O4DVOSLtVW-xA3j--_yQcNsKmFy3BOQEBY6DpZOS5CipB0Zdsv1KOSaNsLCBFFeZem2aAyVNgAAqOO0vLkcyeFeF1dFBEnB6dSlCDZKNex595Pw"

headers = {
    "Authorization": f"Bearer {access_token}"
}

verify_url = "https://api.linkedin.com/v2/userinfo"
response = requests.get(verify_url, headers=headers)

if response.status_code == 200:
    user_data = response.json()
    print("✅ Token Verification Successful!")
    print(f"Your Posting Author URN is: urn:li:person:{user_data.get('sub')}")
    print(f"Account Associated: {user_data.get('name')}")
else:
    print(f"❌ Verification Failed ({response.status_code}):", response.text)