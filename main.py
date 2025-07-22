from fastapi import FastAPI, Request, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import google.oauth2.id_token
from google.auth.transport import requests
from google.cloud import firestore, storage
import starlette.status as status
import datetime
import os
import local_constants
from typing import Optional, List

# Initialize the app
app = FastAPI()

# Firestore client
firestore_db = firestore.Client()

# Storage client
storage_client = storage.Client(project=local_constants.PROJECT_NAME)
bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)

# Firebase auth request adapter
firebase_request_adapter = requests.Request()

# Static files and templates setup
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")

def validate_firebase_token(id_token):
    """Validate Firebase ID token and return user token if valid"""
    if not id_token:
        return None
    
    user_token = None
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(
            id_token, firebase_request_adapter)
    except ValueError as err:
        print(str(err))
    
    return user_token

def get_or_create_user(user_token):
    """Get or create user document in Firestore"""
    user_ref = firestore_db.collection('User').document(user_token['user_id'])
    
    if not user_ref.get().exists:
        # Initialize new user with empty following/followers lists
        user_data = {
            'username': user_token.get('email', '').split('@')[0],
            'email': user_token.get('email', ''),
            'following': [],  # List of user IDs this user follows
            'followers': [],  # List of user IDs following this user
            'created_at': datetime.datetime.now(),
            'profile_pic': None  # Will store path to profile picture in storage
        }
        user_ref.set(user_data)
    
    return user_ref

def upload_image_to_storage(file: UploadFile, user_id: str, folder: str = "posts") -> Optional[str]:
    """Upload an image to Google Cloud Storage and return its public URL"""
    if not file.content_type in ['image/jpeg', 'image/png']:
        return None
    
    # Generate a unique filename
    ext = os.path.splitext(file.filename)[1]
    filename = f"{folder}/{user_id}/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    
    # Upload the file
    blob = bucket.blob(filename)
    blob.upload_from_file(file.file, content_type=file.content_type)
    blob.make_public()
    
    return blob.public_url

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Main timeline page showing posts from user and who they follow"""
    id_token = request.cookies.get("token")
    error_message = "No error here"
    user_token = None
    user_info = None
    
    user_token = validate_firebase_token(id_token)
    if not user_token:
        return templates.TemplateResponse('main.html', {
            'request': request, 
            'user_token': None, 
            'error_message': None, 
            'user_info': None,
            'posts': []
        })
    
    user = get_or_create_user(user_token)
    user_info = user.get().to_dict()
    
    # Get posts from current user and who they follow
    following_ids = user_info.get('following', []) + [user_token['user_id']]
    
    posts_query = firestore_db.collection('Post') \
        .where('UserId', 'in', following_ids) \
        .order_by('Date', direction=firestore.Query.DESCENDING) \
        .limit(50) \
        .stream()
    
    posts = []
    for post in posts_query:
        post_data = post.to_dict()
        post_data['id'] = post.id
        # Get user info for each post
        post_user = firestore_db.collection('User').document(post_data['UserId']).get()
        post_data['user'] = post_user.to_dict()
        posts.append(post_data)
    
    return templates.TemplateResponse('main.html', {
        'request': request, 
        'user_token': user_token, 
        'error_message': error_message, 
        'user_info': user_info,
        'posts': posts
    })

@app.post("/register-user", response_class=RedirectResponse)
async def register_user(request: Request):
    """Endpoint called by firebase-login.js to register new users"""
    id_token = request.cookies.get("token")
    user_token = validate_firebase_token(id_token)
    
    if not user_token:
        return RedirectResponse('/')
    
    # This will create the user if they don't exist
    get_or_create_user(user_token)
    
    return RedirectResponse('/', status_code=status.HTTP_302_FOUND)

@app.get("/profile/{username}", response_class=HTMLResponse)
async def view_profile(request: Request, username: str):
    id_token = request.cookies.get("token")
    user_token = validate_firebase_token(id_token)

    if not user_token:
        return RedirectResponse('/')

    current_user = get_or_create_user(user_token)
    current_user_info = current_user.get().to_dict()

    profile_users = firestore_db.collection('User').where('username', '==', username).limit(1).get()
    if not profile_users:
        return RedirectResponse('/')

    profile_user = profile_users[0]
    profile_user_info = profile_user.to_dict()
    profile_user_info['id'] = profile_user.id

    is_following = user_token['user_id'] in profile_user_info.get('followers', [])

    posts_query = firestore_db.collection('Post') \
        .where('Username', '==', username) \
        .order_by('Date', direction=firestore.Query.DESCENDING) \
        .limit(50) \
        .stream()

    posts = [dict(post.to_dict(), id=post.id) for post in posts_query]

    return templates.TemplateResponse('profile.html', {
        'request': request,
        'user_token': user_token,
        'user_info': current_user_info,
        'current_user': current_user_info,
        'profile_user': profile_user_info,
        'posts': posts,
        'is_own_profile': current_user_info['username'] == profile_user_info['username'],
        'is_following': is_following
    })



@app.post("/follow/{user_id}", response_class=JSONResponse)
async def follow_user(request: Request, user_id: str):
    """Handle follow/unfollow actions"""
    id_token = request.cookies.get("token")
    user_token = validate_firebase_token(id_token)
    
    if not user_token:
        return JSONResponse({'status': 'error', 'message': 'Not authenticated'}, status_code=401)
    
    try:
        # Get the current user document reference
        current_user_ref = firestore_db.collection('User').document(user_token['user_id'])
        current_user = current_user_ref.get()
        
        if not current_user.exists:
            return JSONResponse({'status': 'error', 'message': 'Current user not found'}, status_code=404)
            
        current_user_data = current_user.to_dict()
        
        # Get the user to follow/unfollow
        user_to_follow_ref = firestore_db.collection('User').document(user_id)
        user_to_follow = user_to_follow_ref.get()
        
        if not user_to_follow.exists:
            return JSONResponse({'status': 'error', 'message': 'User not found'}, status_code=404)
            
        user_to_follow_data = user_to_follow.to_dict()
        
        # Check if already following
        is_following = user_id in current_user_data.get('following', [])
        
        # Create a batch for atomic updates
        batch = firestore_db.batch()
        
        if is_following:
            # Unfollow - remove from following/followers
            batch.update(current_user_ref, {
                'following': firestore.ArrayRemove([user_id])
            })
            batch.update(user_to_follow_ref, {
                'followers': firestore.ArrayRemove([user_token['user_id']])
            })
            action = 'unfollowed'
        else:
            # Follow - add to following/followers
            batch.update(current_user_ref, {
                'following': firestore.ArrayUnion([user_id])
            })
            batch.update(user_to_follow_ref, {
                'followers': firestore.ArrayUnion([user_token['user_id']])
            })
            action = 'followed'
        
        # Commit the batch
        await batch.commit()
        
        # Return updated counts
        return JSONResponse({
            'status': 'success',
            'action': action,
            'follower_count': len(user_to_follow_data.get('followers', [])) + (1 if not is_following else -1),
            'following_count': len(current_user_data.get('following', [])) + (1 if not is_following else -1)
        })
        
    except Exception as e:
        print(f"Follow error: {str(e)}")
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: str = None):
    id_token = request.cookies.get("token")
    user_token = validate_firebase_token(id_token)
    
    if not user_token:
        return RedirectResponse('/')
    
    # Get current user document
    current_user_ref = firestore_db.collection('User').document(user_token['user_id'])
    current_user = current_user_ref.get()
    
    results = []
    if q and len(q) > 0:
        users_ref = firestore_db.collection('User')
        query = users_ref.where('username', '>=', q.lower()) \
                        .where('username', '<=', q.lower() + '\uf8ff') \
                        .limit(10) \
                        .stream()
        
        results = [{'id': doc.id, **doc.to_dict()} for doc in query if doc.id != user_token['user_id']]
    
    return templates.TemplateResponse('search.html', {
        'request': request,
        'user_token': user_token,
        'current_user': current_user.to_dict() if current_user.exists else None,
        'query': q,
        'results': results
    })

@app.get("/create-post", response_class=HTMLResponse)
async def show_create_post_page(request: Request):
    """Show the create post form"""
    id_token = request.cookies.get("token")
    user_token = validate_firebase_token(id_token)
    
    if not user_token:
        return RedirectResponse('/')
    
    return templates.TemplateResponse('create_post.html', {
        'request': request,
        'user_token': user_token
    })

@app.post("/create-post", response_class=RedirectResponse)
async def create_post(
    request: Request,
    image: UploadFile = File(...),
    caption: str = Form(...)
):
    """Handle post creation form submission"""
    id_token = request.cookies.get("token")
    user_token = validate_firebase_token(id_token)
    
    if not user_token:
        return RedirectResponse('/')
    
    user = get_or_create_user(user_token)
    user_info = user.get().to_dict()
    
    # Upload image to storage
    image_url = upload_image_to_storage(image, user_token['user_id'])
    if not image_url:
        return RedirectResponse('/create-post?error=invalid_image', status_code=status.HTTP_302_FOUND)
    
    # Create post in Firestore
    post_data = {
        'Username': user_info['username'],
        'UserId': user_token['user_id'],
        'Caption': caption,
        'ImageUrl': image_url,
        'Date': datetime.datetime.now(),
        'Likes': [],
        'Comments': []
    }
    
    firestore_db.collection('Post').add(post_data)
    
    return RedirectResponse(f"/profile/{user_info['username']}", status_code=status.HTTP_302_FOUND)
@app.get("/followers/{username}", response_class=HTMLResponse)
async def view_followers(request: Request, username: str):
    """Show list of followers for a user"""
    id_token = request.cookies.get("token")
    user_token = validate_firebase_token(id_token)
    
    if not user_token:
        return RedirectResponse('/')
    
    current_user = get_or_create_user(user_token)
    current_user_info = current_user.get().to_dict()
    
    # Get the profile being viewed
    profile_users = firestore_db.collection('User').where('username', '==', username).limit(1).get()
    if not profile_users:
        return RedirectResponse('/')
    
    profile_user = profile_users[0]
    profile_user_info = profile_user.to_dict()
    
    # Get followers in reverse chronological order
    followers = []
    for follower_id in profile_user_info.get('followers', []):
        follower = firestore_db.collection('User').document(follower_id).get()
        if follower.exists:
            followers.append(follower.to_dict())
    
    # Sort by when they followed (approximate with user creation date)
    followers.sort(key=lambda x: x.get('created_at', datetime.datetime.min), reverse=True)
    
    return templates.TemplateResponse('followers.html', {
        'request': request,
        'user_token': user_token,
        'current_user': current_user_info,
        'profile_user': profile_user_info,
        'users': followers,
        'list_type': 'followers'
    })

@app.get("/following/{username}", response_class=HTMLResponse)
async def view_following(request: Request, username: str):
    """Show list of users a user is following"""
    id_token = request.cookies.get("token")
    user_token = validate_firebase_token(id_token)
    
    if not user_token:
        return RedirectResponse('/')
    
    current_user = get_or_create_user(user_token)
    current_user_info = current_user.get().to_dict()
    
    # Get the profile being viewed
    profile_users = firestore_db.collection('User').where('username', '==', username).limit(1).get()
    if not profile_users:
        return RedirectResponse('/')
    
    profile_user = profile_users[0]
    profile_user_info = profile_user.to_dict()
    
    # Get following in reverse chronological order
    following = []
    for following_id in profile_user_info.get('following', []):
        followed_user = firestore_db.collection('User').document(following_id).get()
        if followed_user.exists:
            following.append(followed_user.to_dict())
    
    # Sort by when they were followed (approximate with user creation date)
    following.sort(key=lambda x: x.get('created_at', datetime.datetime.min), reverse=True)
    
    return templates.TemplateResponse('following.html', {
        'request': request,
        'user_token': user_token,
        'current_user': current_user_info,
        'profile_user': profile_user_info,
        'users': following,
        'list_type': 'following'
    })

from fastapi.encoders import jsonable_encoder

@app.post("/add-comment/{post_id}", response_class=JSONResponse)
async def add_comment(
    request: Request,
    post_id: str,
    comment_text: str = Form(...)
):
    """Add a comment to a post"""
    id_token = request.cookies.get("token")
    user_token = validate_firebase_token(id_token)
    
    if not user_token:
        return JSONResponse({'status': 'error', 'message': 'Not authenticated'}, status_code=401)
    
    if len(comment_text) > 200:
        return JSONResponse({'status': 'error', 'message': 'Comment too long (max 200 chars)'}, status_code=400)
    
    try:
        user = get_or_create_user(user_token)
        user_info = user.get().to_dict()
        
        comment = {
    'userId': user_token['user_id'],
    'username': user_info['username'],
    'text': comment_text,
    'timestamp': datetime.datetime.now().isoformat()  # Store as ISO string immediately
}
        
        post_ref = firestore_db.collection('Post').document(post_id)
        post_ref.update({
            'Comments': firestore.ArrayUnion([comment])
        })
        
        # Use jsonable_encoder to ensure proper serialization
        return JSONResponse({
            'status': 'success',
            'comment': jsonable_encoder(comment)
        })
        
    except Exception as e:
        print(f"Error adding comment: {str(e)}")
        return JSONResponse({
            'status': 'error', 
            'message': 'Failed to add comment'
        }, status_code=500)

@app.get("/get-comments/{post_id}", response_class=JSONResponse)
async def get_comments(request: Request, post_id: str):
    """Get comments for a post"""
    try:
        post = firestore_db.collection('Post').document(post_id).get()
        if not post.exists:
            return JSONResponse({'status': 'error', 'message': 'Post not found'}, status_code=404)
            
        post_data = post.to_dict()
        comments = post_data.get('Comments', [])
        
        # Convert all timestamps to ISO format strings for consistent sorting
        processed_comments = []
        for comment in comments:
            processed_comment = comment.copy()
            if hasattr(comment['timestamp'], 'isoformat'):
                processed_comment['timestamp'] = comment['timestamp'].isoformat()
            processed_comments.append(processed_comment)
        
        # Sort comments in reverse chronological order using ISO strings
        processed_comments.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return JSONResponse({
            'status': 'success',
            'comments': processed_comments[:5],  # Return first 5 by default
            'total_comments': len(processed_comments)
        })
        
    except Exception as e:
        print(f"Error getting comments: {str(e)}")
        return JSONResponse({'status': 'error', 'message': str(e)}, status_code=500)