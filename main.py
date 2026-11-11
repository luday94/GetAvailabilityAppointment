import argparse
import json
import logging
import logging.handlers
import os
import re
from datetime import datetime
from email.message import EmailMessage

import requests
from dotenv import load_dotenv

from gmail.send_message import gmail_send_message

"""Configuration générale"""
FORMATDATE = "%Y-%m-%d %H:%M:%S"

HEADERSPOSTMAN = {
    "User-Agent": "PostmanRuntime/7.56.1",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0 Safari/537.36"
    )
}

FILE_PATH_HISTO = "./historique.json"
FILE_PATH_LOG = "./message.log"
LEVEL_LOG = logging.INFO


""" Paramètres de configuration du logger """
logging.basicConfig(
    format="[%(asctime)s] %(levelname)-8s : %(message)s",
    level=LEVEL_LOG,
    encoding="utf-8",
    datefmt=FORMATDATE,
)
logger = logging.getLogger("twitter")
handler = logging.handlers.RotatingFileHandler(
    FILE_PATH_LOG, maxBytes=1024000, backupCount=5, encoding="utf-8"
)
handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s] %(levelname)-8s : %(message)s",
        datefmt=FORMATDATE,
    )
)
logger.addHandler(handler)


def get_json(url: str) -> dict:
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


class GetAvailabilityAppointment:
    def get_doctolib_availebility(self, url, consultation_reason):
        """Récupère les rdv depuis les APIs du domain Doctolib si pas
        de corespondance avec consultation_reason extrait les nom des
        motif de consultation mais ne cherche pas si des rdv sont
        disponible

        Parameters
        ----------
        url : string
            Url de la page sur laquel les api doit etre extraite
        consultation_reason : string
            Le motif fourni en argument du main

        Returns
        -------
        tuple
            premier_creneau : dateTime
                Date du premier rdv associé à consultation_reason
            visit_ids : dictionary of string,object
                list des nom des motif de rdv possible pour le practicien
            matched_reason_id : id associé à consultation_reason
        """
        logger.debug("Start get_doctolib_availebility")

        premier_creneau = None
        matched_reason_id = None
        visit_ids = {}

        api_param = re.search("\\/(?P<api_param>[^\\/\\?]*)(\\?|$)", url, re.I | re.M).group(
            "api_param"
        )
        logger.debug(f"API Doctolib trouvée {api_param}")

        data = get_json(
            f"https://www.doctolib.fr/online_booking/api/slot_selection_funnel/v1/info.json?profile_slug={api_param}&locale=fr"
        )
        for visit_motive in data["data"]["visit_motives"]:
            visit_ids[visit_motive["name"]] = visit_motive["id"]
            if visit_motive["name"].strip() == consultation_reason.strip():
                matched_reason_id = visit_motive["id"]
                logger.debug(f"matched_reason_id: {matched_reason_id}")
                break
        if matched_reason_id is not None:
            agenda_id = None
            practice_id = None
            for agenda in data["data"]["agendas"]:
                for i_visit_motive_id in agenda["visit_motive_ids"]:
                    if matched_reason_id == i_visit_motive_id:
                        agenda_id = agenda["id"]
                        logger.debug(f"agenda_id: {agenda_id}")
                        break
                if agenda_id is not None:
                    practice_id = agenda["practice_id"]
                    logger.debug(f"practice_id: {practice_id}")
                    break

            today = datetime.now().strftime("%Y-%m-%d")
            format_api = (
                f"https://www.doctolib.fr/availabilities.json?"
                f"visit_motive_ids={matched_reason_id}"
                f"&agenda_ids={agenda_id}"
                f"&practice_ids={practice_id}"
                f"&telehealth=false"
                f"&start_date={today}"
                f"&limit=15"
            )
            logger.debug(f"format_api: {format_api}")

            # Vérification de la disponibilité
            request = requests.get(format_api, headers=HEADERS)
            data = request.json()
            if data.get("next_slot"):
                premier_creneau = datetime.fromisoformat(data["next_slot"])
                logger.info(f"Premier créneau disponible: {premier_creneau}")
            elif data.get("availabilities") and any(
                availability.get("slots") for availability in data["availabilities"]
            ):
                premier_creneau = next(
                    datetime.fromisoformat(availability["slots"][0])
                    for availability in data["availabilities"]
                    if availability.get("slots")
                )
                logger.info(f"Premier créneau disponible: {premier_creneau}")
            else:
                logger.info("Pas de créneau disponible")
        else:
            logger.warning(f"Aucune raison de consultation trouvée pour {consultation_reason}")
        return premier_creneau, visit_ids, matched_reason_id

    def get_maiia_availebility(self, url, consultation_reason):
        """Récupère les rdv depuis les APIs du domain Maiia si pas
        de corespondance avec consultation_reason extrait les nom des
        motif de consultation mais ne cherche pas si des rdv sont
        disponible

        Parameters
        ----------
        url : string
            Url de la page sur laquel les api doit etre extraite
        consultation_reason : string
            Le motif fourni en argument du main

        Returns
        -------
        tuple
            premier_creneau : dateTime
                Date du premier rdv associé à consultation_reason
            visit_ids : dictionary of string,object
                list des nom des motif de rdv possible pour le practicien
            matched_reason_id : id associé à consultation_reason
        """
        logger.debug("Start get_maiia_availebility")
        premier_creneau = None
        matched_reason_id = None
        visit_ids = {}

        logger.info("API Maiia")
        match_center_id = re.search("centerId=(?P<centerId>[^\\?\\/\\s]*)", url, re.I)
        root_center_id = match_center_id.group("centerId") if match_center_id else ""
        page = requests.get(url, headers=HEADERSPOSTMAN)
        march_speciality_id = re.search(
            '"practitionerId":"(?P<practitionerId>[^"]*)', page.text, re.I
        )
        logger.debug(f"page.text: {page.text}")
        if march_speciality_id is not None:
            speciality_id = march_speciality_id.group("practitionerId")
        else:
            logger.warning("Aucun practitionerId trouvé dans la page")
            speciality_id = ""
        logger.debug(f"speciality_id:{speciality_id}")

        reason_api = (
            "https://www.maiia.com/api/pat-public/consultation-reason-hcd"
            "?checkAvailability=true&limit=200&page=0"
            f"&rootCenterId={root_center_id}"
            f"&practitionerId={speciality_id}"
        )
        availability_api = (
            "https://www.maiia.com/api/pat-public/availability-closests?"
            f"centerId={root_center_id}"
            "&page=0"
            f"&practitionerId={speciality_id}"
        )

        logger.debug(f"reason_api: {reason_api}")
        logger.debug(f"availability_api: {availability_api}")

        # Récupération de l'ID de la raison de consultation
        if reason_api is not None:
            reason_data = get_json(reason_api)
            if reason_data["total"] > 0:
                logger.info("Plusieurs raisons de consultation disponibles")
                for reason_api in reason_data["items"]:
                    visit_ids[reason_api["name"]] = reason_api["id"]
                    # logger.info("Raison: {reason['name']} - ID: {reason['id']}")
                    if reason_api["name"] == consultation_reason:
                        matched_reason_id = reason_api["id"]
                        availability_api = (
                            f"{availability_api}&consultationReasonId={matched_reason_id}"
                        )
                        break
            if matched_reason_id is None:
                logger.debug(
                    f"Raison de consultation '{consultation_reason}' non disponible {visit_ids}"
                )
            else:
                # Vérification de la disponibilité
                availability_data = get_json(availability_api)
                if availability_data["availabilityCount"] > 0:
                    premier_creneau = datetime.strptime(
                        availability_data["firstAvailabilityStartDateTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                    logger.info(f"Premier créneau disponible: {premier_creneau}")
                else:
                    logger.info("Pas de créneau disponible")
        else:
            logger.warning(f"Aucune raison de consultation trouvée pour {consultation_reason}")
        return premier_creneau, visit_ids, matched_reason_id

    def edit_message(
        self,
        url,
        consultation_reason,
        premier_creneau,
        matched_reason_id,
        visit_ids,
        json_historique,
    ):
        """créé le corps du message et retourne
        deux bolléen pour savoir si le message doit etre envoyé

        Parameters
        ----------
        apis : list of string
            List des apis extraite sur la page Url
        consultation_reason : string
            Le motif fourni en argument du main
        premier_creneau : dateTime
            Date du premier rdv associé à consultation_reason
        matched_reason_id : id
            Id associé à consultation_reason
        visit_ids : dictionary of string,object
            List des noms des motifs de rdv possible pour le praticien
        json_historique : dictionary of string,object
            Historique des rdv déjà trouvé pour le praticien

        Returns
        -------
        tuple
            is_alerte_raison : bool
                True si une alerte doit être envoyée pour la raison de consultation.
            is_rdv_trouve : bool
                True si un nouveau rendez-vous a été trouvé.
            message : str
                Le corps du message à envoyer.
        """
        logger.debug("Start edit_message")
        is_alerte_raison, is_rdv_trouve = False, False
        message = ""

        is_in_historique = url in json_historique and consultation_reason in json_historique[url]

        is_nouvel_date = (
            premier_creneau is not None
            and is_in_historique
            and (
                datetime.strptime(
                    json_historique[url][consultation_reason]["date"], FORMATDATE
                ).timestamp()
                > premier_creneau.timestamp()
                or datetime.strptime(
                    json_historique[url][consultation_reason]["date"], FORMATDATE
                ).timestamp()
                < datetime.now().timestamp()
            )
        )

        is_date_deja_envoye = premier_creneau is not None and (
            is_in_historique
            and datetime.strptime(
                json_historique[url][consultation_reason]["date"], FORMATDATE
            ).timestamp()
            <= premier_creneau.timestamp()
        )
        # Si nouveaux rdv
        if (premier_creneau is not None and not is_in_historique) or is_nouvel_date:
            is_rdv_trouve = True
            message = (
                f"Créneau pour {consultation_reason} disponible le: "
                f"{premier_creneau.strftime(FORMATDATE)}\n{url}"
            )
        elif is_date_deja_envoye:
            logger.info("Un mail à déjà été envoyé")

        # Si la raison fournie n'est pas bonne alors la fournir si elle exite à l'utilisateur
        if (
            matched_reason_id is None
            and visit_ids.keys().__len__() > 0
            and not (
                url in json_historique
                and consultation_reason in json_historique[url]
                and json_historique[url][consultation_reason]["is_alerte_raison"]
            )
        ):
            logger.warning(
                "Aucune correspondance trouvée pour "
                f"la raison de consultation: {consultation_reason}"
            )
            is_alerte_raison = True
            list_reasons = ("\n-").join(visit_ids.keys())
            message = (
                f"Attention! Pas de correspondance entre:\n-{consultation_reason}\n"
                f"Et la list suivant:\n-{list_reasons}\n"
                "Veuillez vériffier l'argument "
                f"CONSULTATION_REASON fournie\n{message}"
            )
        elif matched_reason_id is None and visit_ids.keys().__len__() > 0:
            logger.info("Un mail d'alerte à déjà été envoyé")
        return is_alerte_raison, is_rdv_trouve, message

    def main(self, url, consultation_reason):
        logger.debug(f"Start main: url: {url}, consultation_reason: {consultation_reason}")
        logger.info("Début du script")

        domain = re.search(
            "^(?:https?:\\/\\/)?(?:[^@\\/\\n]+@)?(?:www\\.)?([^:\\/\\n]+)", url
        ).group(1)

        if domain == "doctolib.fr":
            """ Doctolib API """
            premier_creneau, visit_ids, matched_reason_id = self.get_doctolib_availebility(
                url, consultation_reason
            )

        elif domain == "maiia.com":
            """ Maiia API """
            premier_creneau, visit_ids, matched_reason_id = self.get_maiia_availebility(
                url, consultation_reason
            )

        if os.path.exists(FILE_PATH_HISTO):
            with open(FILE_PATH_HISTO) as file:
                read = file.read()
                json_historique = json.loads(read)
        else:
            json_historique = {}

        """ Structure du message """
        is_alerte_raison, is_rdv_trouve, message = self.edit_message(
            url, consultation_reason, premier_creneau, matched_reason_id, visit_ids, json_historique
        )

        """Envoi du mail via l'API Gmail si contient un message"""
        if is_alerte_raison or is_rdv_trouve:
            try:
                msg = EmailMessage()
                msg["Subject"] = (
                    (f"[{domain}] - Créneau disponible {datetime.now():%Y-%m-%d %H:%M:%S}")
                    if is_rdv_trouve
                    else f"[{domain}] - Erreur dans CONSULTATION_REASON fournie"
                )
                msg["To"] = "ludovictaut@gmail.com"
                msg.set_content(message)
                gmail_send_message(msg)
                logger.info("Email envoyé via API Gmail")
                if url not in json_historique:
                    json_historique[url] = {}
                json_historique[url][consultation_reason] = {
                    "date": premier_creneau.strftime(FORMATDATE)
                    if premier_creneau is not None
                    else datetime.now().strftime(FORMATDATE),
                    "is_alerte_raison": is_alerte_raison,
                    "is_rdv_trouve": is_rdv_trouve,
                }

                with open(FILE_PATH_HISTO, "w+") as file:
                    file.write(json.dumps(json_historique, indent=4))

            except Exception as e:
                logger.Error(f"{e}")


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser()

    parser.add_argument("--url", default=os.getenv("URL"))

    parser.add_argument("--consultation-reason", default=os.getenv("CONSULTATION_REASON"))

    args = parser.parse_args()

    if not args.url:
        args.url = input("URL : ")

    if not args.consultation_reason:
        args.consultation_reason = input("Motif : ")

    GetAvailabilityAppointment().main(args.url, args.consultation_reason)
