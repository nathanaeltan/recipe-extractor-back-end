import requests

API_URL = "https://api.data.gov.sg/v1/environment/water-level"
response = requests.get(API_URL)
data = response.json()
print(data)
for station in data["items"][0]["readings"]:
    if station["value"] > 0.8:  # 80% water level threshold
        print(f"⚠️ Flood risk detected at {station['station_id']}!")
