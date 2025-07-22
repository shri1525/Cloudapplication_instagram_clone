# Cloud application_instagram_clone

A full-stack Instagram clone built with **Python (FastAPI)**, **HTML/CSS (Jinja2 templates)**, **Google Cloud (Firestore & Storage)**, and **Firebase Authentication**. This app supports user registration, login, profile management, creating posts with image upload, commenting, user following, and more—running entirely on the cloud.

## Features

- **User Authentication**: Secure login and registration using Firebase Auth.
- **User Profiles**: Personalized profiles, viewable by others.
- **Image Posts**: Upload images with captions to your feed; images are stored on Google Cloud Storage.
- **Feed/TIMELINE**: See your posts and those from users you follow.
- **Follow/Unfollow**: Follow other users and build your network.
- **Comments**: Comment on posts with real-time updates.
- **Search**: Find users by username.
- **Cloud Native**: Fully serverless backend using Firestore and Storage.

## Tech Stack

| Component    | Details                          |
|--------------|----------------------------------|
| Backend      | FastAPI (Python)                 |
| Frontend     | HTML/CSS, Jinja2                 |
| Database     | Google Firestore                 |
| Storage      | Google Cloud Storage             |
| Auth         | Firebase Authentication (Google) |
| Deployment   | Cloud/serverless-friendly        |

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/instagram-clone-cloud.git
cd instagram-clone-cloud
```

### 2. Install Dependencies

Create a virtual environment and install requirements:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Google Cloud

- Set up a Google Cloud project.
- Enable Firestore and Cloud Storage.
- Download your `serviceAccountKey.json` or set up ADC (for authentication).
- Set environment variables or create `local_constants.py` with:
  - `PROJECT_NAME`
  - `PROJECT_STORAGE_BUCKET`

### 4. Firebase Authentication

- Go to [Firebase console](https://console.firebase.google.com/).
- Register your app.
- Enable Email/Password sign-in.
- Get the Firebase web config (needed for frontend login JS).

### 5. Update Configuration

- Place credentials in the root or configure Docker/Cloud secrets as needed.
- Edit `local_constants.py` for your project.

### 6. Initialize Firestore Collections

Firestore collections required:
- `User`
- `Post`

Default structure for User:
```json
{
  "username": "string",
  "email": "string",
  "following": [],
  "followers": [],
  "created_at": "timestamp",
  "profile_pic": "string or null"
}
```
Default structure for Post:
```json
{
  "Username": "string",
  "UserId": "string",
  "Caption": "string",
  "ImageUrl": "string",
  "Date": "timestamp",
  "Likes": [],
  "Comments": []
}
```

### 7. Run the Application

```bash
uvicorn main:app --reload
```

### 8. Access

Go to `http://localhost:8000` in your browser. Register and start posting!

## Folder Structure

```
.
├── main.py
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── main.html
│   ├── profile.html
│   └── ...
├── static/
│   ├── styles.css
│   └── ...
├── local_constants.py
├── ...
```

## Major Endpoints

- `/` — Main timeline (feeds)
- `/profile/{username}` — User profile
- `/create-post` — New post (image & caption)
- `/follow/{user_id}` — Follow/unfollow a user (POST)
- `/followers/{username}` — List followers
- `/following/{username}` — List followings
- `/add-comment/{post_id}` — Add comment (AJAX POST)
- `/get-comments/{post_id}` — Fetch comments (AJAX GET)
- `/search?q=...` — User search

## Contributing

Willing to improve the clone? Pull requests are welcome! Please open an issue to highlight bugs or propose features.

## License

This project is licensed under the MIT License.

## Notes

- Remember to secure your credentials and never commit secret keys.
- For production, configure HTTPS, environment variable management, and restrict CORS as needed.
- The project is designed for learning/demo use and is not intended for production as-is.

