import base64
from email.message import EmailMessage

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def gmail_send_message(msg: EmailMessage):
  """Create and send an email message
  Print the returned  message id
  Returns: Message object, including message id

  Load pre-authorized user credentials from the environment.
  TODO(developer) - See https://developers.google.com/identity
  for guides on implementing OAuth2 for the application.
  """

  SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

  creds = Credentials.from_authorized_user_file(
      "token.json",
      SCOPES
  )

  try:
    service = build("gmail", "v1", credentials=creds)

    # encoded message
    encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    create_message = {"raw": encoded_message}
    # pylint: disable=E1101
    send_message = (
        service.users()
        .messages()
        .send(userId="me", body=create_message)
        .execute()
    )
    print(f'Message Id: {send_message["id"]}')
  except HttpError as error:
    print(f"An error occurred: {error}")
    send_message = None
  return send_message


if __name__ == "__main__":
  message=EmailMessage()
  message['Subject'] = "Test mail par API"
  message.set_content("Ce message est envoyé par l'API Gmail pour des tests")
  message["To"] = "ludovictaut@gmail.com"
  gmail_send_message(message)