#!/usr/bin/env python3
import sys
import os
import requests
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive


def authenticate(email, password):
    """
    Authenticate the user and retrieve the session ID (JWT token).
    """
    auth_url = "https://edocperso.fr/index.php?api=Authenticate&a=doAuthentication"
    payload = {"login": email, "password": password}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(auth_url, json=payload, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        raise Exception(f"Error during authentication on eDocPerso: {e}")

    try:
        data = response.json()
        login_url = data["content"]["loginUrl"]
    except (KeyError, ValueError) as e:
        raise Exception(f"Error parsing authentication response: {e}")

    # Retrieve the session ID by removing the prefix
    prefix = "https://v2-app.edocperso.fr/login/"
    if login_url.startswith(prefix):
        session_id = login_url[len(prefix) :]
    else:
        session_id = login_url

    return session_id


def retrieve_documents(session_id):
    """
    Retrieve the list of documents using the session ID.
    """
    docs_url = "https://v2-app.edocperso.fr/edocPerso/V1/edpDoc/getLast"
    payload = {"sessionId": session_id}
    headers = {
        "Authorization": f"Bearer {session_id}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(docs_url, json=payload, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        raise Exception(f"Error retrieving documents: {e}")

    try:
        data = response.json()
        docs_list = data["content"]["edpDocs"]
    except (KeyError, ValueError) as e:
        raise Exception(f"Error parsing documents response: {e}")

    return docs_list


def load_downloaded_ids(file_path):
    """
    Load downloaded document IDs (using folder-file combination) from the specified file.
    """
    print("print file_path", file_path)
    downloaded_ids = set()
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                for line in f:
                    downloaded_ids.add(line.strip())
        except IOError as e:
            raise Exception(f"Error reading file {file_path}: {e}")
    return downloaded_ids


def update_downloaded_ids(file_path, identifier):
    """
    Append a new downloaded file identifier (folder_id_file_id) to the specified file.
    """
    try:
        with open(file_path, "a") as f:
            f.write(identifier + "\n")
    except IOError as e:
        print(f"Error updating {file_path}: {e}")


def download_document(doc, session_id, downloaded_ids, downloaded_file):
    """
    Download the document if it has not been downloaded already.
    Uses the folder ID and file ID combination as a unique identifier.
    """
    folder_id = doc.get("folderId", "no_folder")
    file_id = doc["id"]
    # Create the unique identifier as a combination of folderId and file id
    file_identifier = f"{folder_id}_{file_id}"
    name = doc["name"]

    if file_identifier in downloaded_ids:
        print(f"Document already downloaded from eDocPerso, skipping: {name}")
        return

    # Create a valid file name by replacing spaces and "/" with "_"
    file_name = name.replace(" ", "_").replace("/", "_") + ".pdf"

    download_url = (
        f"https://v2-app.edocperso.fr/edocPerso/V1/edpDoc/getDocContent"
        f"?sessionId={session_id}&documentId={file_id}"
    )

    print(f"Downloading '{name}' into '{file_name}'...")
    try:
        response = requests.get(
            download_url, headers={"Authorization": f"Bearer {session_id}"}
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error downloading document {name}: {e}")
        return

    try:
        with open(file_name, "wb") as f:
            f.write(response.content)
        print(f"Download of '{name}' successful.")
    except IOError as e:
        print(f"Error writing file {file_name}: {e}")
        return

    update_downloaded_ids(downloaded_file, file_identifier)


def main():
    # Verify that the required arguments are provided
    # if len(sys.argv) < 3:
    #     print("Usage: {} <email> <password>".format(sys.argv[0]))
    #     sys.exit(1)

    # Onlt in development
    # email = sys.argv[1]
    # password = sys.argv[2]

    # Only in production
    try:
        with open("/run/secrets/my_secrets", "r") as f:
            mon_secret = f.read().strip()
    except Exception as e:
        print(f"Erreur lors de la lecture du secret : {e}")
        sys.exit(1)

    try:
        email, password = mon_secret.splitlines()
    except ValueError:
        print(
            "Le secret doit contenir l'email et le mot de passe sur deux lignes distinctes."
        )
        sys.exit(1)

    # Authenticate and retrieve session ID
    try:
        session_id = authenticate(email, password)
        print("Authentication successful on eDocPerso.")
    except Exception as e:
        print(e)
        sys.exit(1)

    # Retrieve the list of documents
    try:
        docs_list = retrieve_documents(session_id)
    except Exception as e:
        print(e)
        sys.exit(1)

    # Display the retrieved documents
    print("Retrieved documents form eDocPerso:")
    for doc in docs_list:
        print(doc["id"], doc["name"])

    # Load downloaded document IDs from file
    downloaded_file = "downloaded.txt"
    try:
        downloaded_ids = load_downloaded_ids(downloaded_file)
    except Exception as e:
        print(e)
        sys.exit(1)

    # Download documents that have not been downloaded yet
    for doc in docs_list:
        download_document(doc, session_id, downloaded_ids, downloaded_file)

    # Save the new downloaded documents in my folder "bulletins_de_paie" in my Google Drive
    # Authenticate and create Google Drive instance
    gauth = GoogleAuth()
    gauth.settings["client_config_backend"] = "service"
    gauth.settings["service_config"] = {
        "client_json_file_path": "google_info.json",
        "client_user_email": "",
    }
    gauth.ServiceAuth()
    drive = GoogleDrive(gauth)

    # Create a folder named "bulletins_de_paie" if it doesn't exist
    folder_name = "bulletins_de_paie"
    folder_list = drive.ListFile(
        {
            "q": f"title='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        }
    ).GetList()

    if folder_list:
        folder = folder_list[0]
        print(
            "The folder '%s' already exists with the id: %s"
            % (folder_name, folder["id"])
        )
    else:
        folder_metadata = {
            "title": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = drive.CreateFile(folder_metadata)
        folder.Upload()
        print("File '%s' created with the id: %s" % (folder_name, folder["id"]))

    # Give all permissions to kohsey.dufour@gmail.com
    folder.InsertPermission(
        {"type": "user", "value": "kohsey.dufour@gmail.com", "role": "writer"}
    )

    # Upload downloaded documents to Google Drive
    local_downloads_folder = os.getcwd()

    # Load files from "uploaded.txt"
    uploaded_log_file = "uploaded.txt"
    uploaded_ids = set()
    if os.path.exists(uploaded_log_file):
        try:
            with open(uploaded_log_file, "r") as f:
                for line in f:
                    uploaded_ids.add(line.strip())
        except Exception as e:
            print(f"Error reading {uploaded_log_file}: {e}")

    # Upload not already uploaded PDF files to Google Drive
    for file in os.listdir(local_downloads_folder):
        if file.lower().endswith(".pdf"):
            if file in uploaded_ids:
                print(f"Document '{file}' already uploaded on Google Drive, skipping.")
                continue
            file_path = os.path.join(local_downloads_folder, file)
            gfile = drive.CreateFile({"title": file, "parents": [{"id": folder["id"]}]})
            gfile.SetContentFile(file_path)
            try:
                gfile.Upload()
                print(
                    "Uploaded document '%s' with id: %s in Google Drive."
                    % (file, gfile["id"])
                )
                # Add the uploaded file to log
                with open(uploaded_log_file, "a") as f:
                    f.write(file + "\n")
            except Exception as e:
                print(f"Error uploading {file} in Google Drive: {e}")


if __name__ == "__main__":
    main()
