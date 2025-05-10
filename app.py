from flask import Flask, request, jsonify
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os

app = Flask(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/drive'
]
SERVICE_ACCOUNT_FILE = 'service_account.json'

# 👇 Replace this with your personal Google account to receive access
USER_EMAIL_TO_SHARE = 'grao@ideo.com'


@app.route('/')
def home():
    return "✅ Flask server is running!"


@app.route('/create-deck', methods=['POST'])
def create_deck():
    print("✅ Received request!")

    try:
        data = request.get_json()
        print("📦 JSON Payload:", data)

        if not data:
            return jsonify({"error": "No JSON received"}), 400

        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        slides_service = build('slides', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)

        # Create new presentation
        presentation = slides_service.presentations().create(body={'title': data['title']}).execute()
        presentation_id = presentation['presentationId']
        print(f"📄 Created presentation ID: {presentation_id}")

        # Share with your Google account
        print(f"🔗 Sharing with {USER_EMAIL_TO_SHARE}")
        drive_service.permissions().create(
            fileId=presentation_id,
            body={
                'type': 'user',
                'role': 'writer',
                'emailAddress': USER_EMAIL_TO_SHARE
            },
            fields='id'
        ).execute()

        for slide in data['slides']:
            # 1. Create slide using TITLE_AND_BODY layout
            slide_response = slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': [{
                    'createSlide': {
                        'slideLayoutReference': {'predefinedLayout': 'TITLE_AND_BODY'}
                    }
                }]}
            ).execute()

            slide_id = slide_response['replies'][0]['createSlide']['objectId']
            print(f"🧩 Created slide ID: {slide_id}")

            # 2. Get placeholder object IDs
            presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
            slides = presentation.get('slides')
            latest_slide = slides[-1]

            title_placeholder_id = None
            for element in latest_slide['pageElements']:
                if 'shape' in element and element['shape'].get('placeholder', {}).get('type') == 'TITLE':
                    title_placeholder_id = element['objectId']
                    break

            print(f"🔠 Title placeholder ID: {title_placeholder_id}")

            # 3. Build text insert requests
            requests = []

            if title_placeholder_id:
                requests.append({
                    'insertText': {
                        'objectId': title_placeholder_id,
                        'text': slide['title'],
                        'insertionIndex': 0
                    }
                })

            # 4. Add bullet points in a new text box
            if slide.get('bullets'):
                text = '\n'.join(slide['bullets'])
                box_id = f"{slide_id}_bullets"

                requests += [
                    {
                        'createShape': {
                            'objectId': box_id,
                            'shapeType': 'TEXT_BOX',
                            'elementProperties': {
                                'pageObjectId': slide_id,
                                'size': {
                                    'height': {'magnitude': 3000000, 'unit': 'EMU'},
                                    'width': {'magnitude': 4000000, 'unit': 'EMU'}
                                },
                                'transform': {
                                    'scaleX': 1,
                                    'scaleY': 1,
                                    'translateX': 1000000,
                                    'translateY': 1500000,
                                    'unit': 'EMU'
                                }
                            }
                        }
                    },
                    {
                        'insertText': {
                            'objectId': box_id,
                            'insertionIndex': 0,
                            'text': text
                        }
                    },
                    {
                        'createParagraphBullets': {
                            'objectId': box_id,
                            'textRange': {'type': 'ALL'},
                            'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                        }
                    }
                ]

            # 5. Apply the updates
            slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ).execute()

        return jsonify({
            "status": "success",
            "url": f"https://docs.google.com/presentation/d/{presentation_id}"
        })

    except Exception as e:
        print("🔥 Exception occurred:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
