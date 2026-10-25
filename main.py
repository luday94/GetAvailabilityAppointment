import requests
from datetime import datetime
from email.message import EmailMessage
from gmail.send_message import gmail_send_message
from playwright.sync_api import sync_playwright
import re


def nowstr():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f"{nowstr()}: Début du script")

url="https://www.maiia.com/dermatologue-et-venerologue/94130-nogent-sur-marne/fardet-professeur-laurence"
# reasonfinded = "Consultation de suivi"
reasonfinded = "Première consultation"

# url="https://www.maiia.com/medecin-generaliste/75013-paris-13e/srour-nariyanne?centerId=6a1d62b91665bef49231d513"
# # reasonfinded = "Consultation de suivi"
# reasonfinded = "Renouvellement d'ordonnance"
# url="https://www.doctolib.fr/dermatologue/nogent-sur-marne/michael-naouri"
# reasonfinded = "Fotofinder - Cartographie numérique de l'ensemble des grains de beauté assistée par intelligence artificielle + Examen dermatologique de dépistage"

""""
 Récupération des API de la page
"""
apis=[]
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page()
    # f=open("cookies.json", "w+")
    # Extraction API de la page
    def log_request(request):
        if "api/" in request.url :
            # print(f"{nowstr()}: {request.url}", file=f)
            apis.append(request.url)
    page.on("request", log_request)

    page.goto(url)
    for i in range(10):
        page.wait_for_timeout(600)
        if len(apis) > 0:
            break
    browser.close()
    # f.close()

premiercreneau=None
domain=re.search("^(?:https?:\\/\\/)?(?:[^@\\/\\n]+@)?(?:www\\.)?([^:\\/\\n]+)",url).group(1)


if not apis:
    print(f"{nowstr()}: Aucune API trouvée")
    exit(1)
elif domain == "doctolib.fr":
    """
    Doctolib API
    Récupération des l'ID de la consultation
    """
    print(f"{nowstr()}: API Doctolib trouvée")
    request=requests.get(apis[0])
    data = request.json()
    for visit_motive in data["data"]["visit_motives"]:
        if visit_motive["name"] == reasonfinded:
            visit_motive_id = visit_motive["id"]
            # print (f"Raison de consultation {reasonfinded} trouvée avec l'ID: {visit_motive_id}")
            break
    agenda_id=None
    practice_id=None
    for agenda in data["data"]["agendas"]:
        for i_visit_motive_id in agenda["visit_motive_ids"]:
            if visit_motive_id == i_visit_motive_id:
                agenda_id = agenda["id"]
                break
        if agenda_id is not None:
            practice_id = agenda["practice_id"]
            break
    
    today=datetime.now().strftime("%Y-%m-%d")
    formatapi=f"https://www.doctolib.fr/availabilities.json?visit_motive_ids={visit_motive_id}&agenda_ids={agenda_id}&practice_ids={practice_id}&telehealth=false&start_date={today}&limit=15"
    headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0 Safari/537.36"
        )
    }

    # Vérification de la disponibilité
    request=requests.get(formatapi, headers=headers)
    data = request.json()
    if data.get("next_slot"):
        premiercreneau=data["next_slot"]
        print(f"{nowstr()}: Premier créneau disponible: {premiercreneau}")
    else:
        print("Pas de créneau disponible")
    # print(f"{nowstr()}: API créneau: {formatapi}")  

elif domain == "maiia.com":
    """
    Maiia API
    """
    print(f"{nowstr()}: API Maiia trouvée")
    reason= next((api for api in apis if "reason" in api), None)
    availability=next((api for api in apis if "availability" in api), None)
    if not availability:
        print(f"{nowstr()}: API availability non trouvée")
        exit(1)
    APIavailability=availability

    # Récupération de l'ID de la raison de consultation
    if reason is not None:
        response=requests.get(reason)
        data = response.json()
        if data["total"]>0:
            print(f"{nowstr()}: Plusieurs raisons de consultation disponibles")
            for reason in data["items"]:
                # print(f"{nowstr()}: Raison: {reason['name']} - ID: {reason['id']}")
                if reason["name"] == reasonfinded:
                    idreasonfinded = reason["id"]
                    APIavailability=f"{APIavailability}&consultationReasonId={idreasonfinded}"
                    break
        if "consultationReasonId" not in APIavailability:
            print(f"{nowstr()}: Raison de consultation {reasonfinded} non disponible")
    else:
        print(f"{nowstr()}: Aucune raison de consultation trouvée")

    # Vérification de la disponibilité
    response=requests.get(APIavailability)
    data = response.json()
    if data["availabilityCount"] > 0:
        premiercreneau=data["firstAvailabilityStartDateTime"]
        print(f"{nowstr()}: Premier créneau disponible: {premiercreneau}")
    else:
        print(f"{nowstr()}: Pas de créneau disponible")



"""
 Structure et envoie du mail 
"""

msg=EmailMessage()
# msg['Subject'] = "Test mail par API"
msg['Subject'] = f"Créneau disponible {datetime.now():%Y-%m-%d %H:%M:%S}"
msg["To"] = "ludovictaut@gmail.com"


if premiercreneau:
    print(f"{nowstr()}: Créneau pour {reasonfinded} disponible le {premiercreneau}")
    msg.set_content(f'Créneau pour {reasonfinded} disponible le: {premiercreneau}\n{url}')
    # Envoi du mail via l'API Gmail
    try:
        gmail_send_message(msg) 
        print(f"{nowstr()}: Email envoyé via API Gmail")
    except Exception as e:
        print(f"{nowstr()}: Erreur : {e}")