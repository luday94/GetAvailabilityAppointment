import requests
import os
from dotenv import load_dotenv
from datetime import datetime
from email.message import EmailMessage
from gmail.send_message import gmail_send_message

url="https://www.maiia.com/dermatologue-et-venerologue/94130-nogent-sur-marne/fardet-professeur-laurence"
reasonfinded = "Consultation de suivi"
# reasonfinded = "Première consultation"

# url="https://www.maiia.com/medecin-generaliste/75013-paris-13e/srour-nariyanne?centerId=6a1d62b91665bef49231d513"
# # reasonfinded = "Consultation de suivi"
# reasonfinded = "Renouvellement d'ordonnance"

from playwright.sync_api import sync_playwright
apis = {
    "reason": None,
    "availability": None
}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page()
    f=open("cookies.json", "w+")
    def log_request(request):
        if "api/" in request.url and "reason" in request.url:
            apis["reason"] = request.url
            # print (f"API reason: {request.url}")
        if "api/" in request.url and "availability" in request.url:
            apis["availability"] = request.url
            # print (f"API availability: {request.url}")
    page.on("request", log_request)

    page.goto(url)

    delay= 5000  # Délai en millisecondes
    page.wait_for_timeout(delay)
    browser.close()
    f.close()
print("Reason :", apis["reason"])
print("Availability :", apis["availability"])
load_dotenv(".env.test")
"""
 Structure du mail 
"""
msg = EmailMessage()
msg['Subject'] = f"Créneau disponible {datetime.now():%Y-%m-%d %H:%M:%S}"
msg['From'] = os.getenv("DB_USER")
msg['To'] = os.getenv("DB_TOMAILMESSAGE")



# Get API reason
response=requests.get(apis["reason"])
data = response.json()
idreasonfinded = None
APIavailability=apis["availability"]
if data["total"]>0:
    print("Plusieurs raisons de consultation disponibles")
    for reason in data["items"]:
        print(f"Raison: {reason['name']} - ID: {reason['id']}")
        if reason["name"] == reasonfinded:
            idreasonfinded = reason["id"]
            APIavailability=f"{APIavailability}&consultationReasonId={idreasonfinded}"
            break
            

if "consultationReasonId" not in APIavailability:
    print(f"Raison de consultation {reasonfinded} non disponible")
    # exit(1)



response=requests.get(APIavailability)
data = response.json()


# Si disponibilité ?
if data["availabilityCount"] > 0:
    
    print(f"Créneau pour {reasonfinded} disponible")
    msg.set_content(f'Créneau pour {reasonfinded} disponible:\n{url}')
    # Envoi du mail via l'API Gmail
    try:
        gmail_send_message(msg) 
        print("Email envoyé via API Gmail")
    except Exception as e:
        print(f"Erreur : {e}")

else:
    print("Pas de créneau disponible")
