import json
import os
import re
import sys
from datetime import datetime
from email.message import EmailMessage

import requests
from playwright.sync_api import sync_playwright

from gmail.send_message import gmail_send_message

FORMATDATE = "%Y-%m-%d %H:%M:%S"


def now_str():
    """now_str

    Returns:
        str: revoir a la date actuel en string
    """
    return datetime.now().strftime(FORMATDATE)


print(f"{now_str()}: Début du script")

# url="https://www.maiia.com/dermatologue-et-venerologue/94130-nogent-sur-marne/fardet-professeur-laurence"
# reasonfinded = "Consultation de suivi"
# # reasonfinded = "Première consultation"

url = "https://www.maiia.com/medecin-generaliste/75013-paris-13e/srour-nariyanne?centerId=6a1d62b91665bef49231d513"
# reasonfinded = "Consultation de suivi"
consultation_reason = "Renouvellement d'ordonnance"
# url="https://www.doctolib.fr/dermatologue/nogent-sur-marne/michael-naouri"
reasonfinded = (
    "Fotofinder - Cartographie numérique de l'ensemble des "
    "grains de beauté assistée par intelligence artificielle "
    "Examen dermatologique de dépistage"
)
""""
Récupération des API de la page
"""
apis = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    def log_request(request):
        if "api/" in request.url:
            # print(f"{now_str()}: {request.url}", file=f)
            apis.append(request.url)

    page.on("request", log_request)
    page.goto(url)
    for i in range(10):
        page.wait_for_timeout(600)
        if len(apis) > 0:
            break
    browser.close()
    # f.close()

premier_creneau = None
domain = re.search("^(?:https?:\\/\\/)?(?:[^@\\/\\n]+@)?(?:www\\.)?([^:\\/\\n]+)", url).group(1)

file_path_histo = "./historique.json"

if os.path.exists(file_path_histo):
    with open(file_path_histo) as file:
        read = file.read()
        json_historique = json.loads(read)
else:
    json_historique = {}

if not apis:
    print(f"{now_str()}: Aucune API trouvée")
    sys.exit(1)
elif domain == "doctolib.fr":
    """
    Doctolib API
    Récupération des l'ID de la consultation
    """
    print(f"{now_str()}: API Doctolib trouvée")
    request = requests.get(apis[0])
    data = request.json()
    for visit_motive in data["data"]["visit_motives"]:
        if visit_motive["name"] == consultation_reason:
            visit_motive_id = visit_motive["id"]
            # print (f"Raison de consultation {reasonfinded} trouvée avec l'ID: {visit_motive_id}")
            break
    agenda_id = None
    practice_id = None
    for agenda in data["data"]["agendas"]:
        for i_visit_motive_id in agenda["visit_motive_ids"]:
            if visit_motive_id == i_visit_motive_id:
                agenda_id = agenda["id"]
                break
        if agenda_id is not None:
            practice_id = agenda["practice_id"]
            break

    today = datetime.now().strftime("%Y-%m-%d")
    formatapi = (
        f"https://www.doctolib.fr/availabilities.json?visit_motive_ids="
        f"&{visit_motive_id}"
        f"&agenda_ids={agenda_id}"
        f"&practice_ids={practice_id}"
        f"&telehealth=false"
        f"&start_date={today}"
        f"&limit=15"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/141.0 Safari/537.36"
        )
    }

    # Vérification de la disponibilité
    request = requests.get(formatapi, headers=headers)
    data = request.json()
    if data.get("next_slot"):
        premier_creneau = data["next_slot"]
        print(f"{now_str()}: Premier créneau disponible: {premier_creneau}")
    elif data.get("availabilities"):
        premier_creneau = datetime.strptime(
            data["availabilities"][0]["solts"][0], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        print(f"{now_str()}: Premier créneau disponible: {premier_creneau}")
    else:
        print("Pas de créneau disponible")
    # print(f"{now_str()}: API créneau: {formatapi}")

elif domain == "maiia.com":
    """
    Maiia API
    """
    print(f"{now_str()}: API Maiia trouvée")
    reason = next((api for api in apis if "reason" in api), None)
    availability = next((api for api in apis if "availability" in api), None)
    if not availability:
        print(f"{now_str()}: API availability non trouvée")
        sys.exit(1)
    APIavailability = availability

    # Récupération de l'ID de la raison de consultation
    if reason is not None:
        response = requests.get(reason)
        data = response.json()
        if data["total"] > 0:
            print(f"{now_str()}: Plusieurs raisons de consultation disponibles")
            for reason in data["items"]:
                # print(f"{now_str()}: Raison: {reason['name']} - ID: {reason['id']}")
                if reason["name"] == consultation_reason:
                    matched_reason_id = reason["id"]
                    APIavailability = f"{APIavailability}&consultationReasonId={matched_reason_id}"
                    break
        if "consultationReasonId" not in APIavailability:
            print(f"{now_str()}: Raison de consultation {consultation_reason} non disponible")
    else:
        print(f"{now_str()}: Aucune raison de consultation trouvée")

    # Vérification de la disponibilité
    response = requests.get(APIavailability)
    data = response.json()
    if data["availabilityCount"] > 0:
        premier_creneau = datetime.strptime(
            data["firstAvailabilityStartDateTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        print(f"{now_str()}: Premier créneau disponible: {premier_creneau}")
    else:
        print(f"{now_str()}: Pas de créneau disponible")

"""
Structure et envoie du mail
"""

msg = EmailMessage()
msg["Subject"] = f"Créneau disponible {datetime.now():%Y-%m-%d %H:%M:%S}"
msg["To"] = "ludovictaut@gmail.com"

url_et_motif_consult = url + "\\" + consultation_reason
if premier_creneau is not None and (
    (url_et_motif_consult not in json_historique)
    or (
        url_et_motif_consult in json_historique
        and (
            datetime.strptime(json_historique[url_et_motif_consult], FORMATDATE) > premier_creneau
            or datetime.strptime(json_historique[url_et_motif_consult], FORMATDATE) < datetime.now()
        )
    )
):
    print(
        f"{now_str()}: Créneau pour {consultation_reason} "
        f"disponible le {premier_creneau.strftime(FORMATDATE)}"
    )
    msg.set_content(
        f"Créneau pour {consultation_reason} disponible le: "
        f"{premier_creneau.strftime(FORMATDATE)}\n{url}"
    )
    # Envoi du mail via l'API Gmail
    try:
        gmail_send_message(msg)
        print(f"{now_str()}: Email envoyé via API Gmail")
        json_historique[url_et_motif_consult] = premier_creneau.strftime(FORMATDATE)
        with open(file_path_histo, "w+") as file:
            file.write(json.dumps(json_historique, indent=4))

    except Exception as e:
        print(f"{now_str()}: Erreur : {e}")
elif (
    premier_creneau is not None
    and url_et_motif_consult in json_historique
    and datetime.strptime(json_historique[url_et_motif_consult], FORMATDATE) <= premier_creneau
):
    print(f"{now_str()}: Un mail à déjà été envoyé")
