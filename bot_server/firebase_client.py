import firebase_admin
from firebase_admin import credentials, firestore
import os
import uuid

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK.
    """
    # Get the service account key path from an environment variable for security.
    # The user should set this environment variable to '/home/rolando/archivo.json'
    cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH")

    if not cred_path:
        # Fallback to the hardcoded path if the environment variable is not set.
        # This is not recommended for production.
        cred_path = "/home/rolando/archivo.json"

    if not os.path.exists(cred_path):
        print(f"Error: Firebase service account key not found at {cred_path}")
        print("Please make sure the file exists or set the FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable.")
        return None

    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            print("Firebase app initialized successfully.")
        return firestore.client()
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return None

db = initialize_firebase()

def get_db():
    """
    Returns the Firestore database client.
    """
    return db

def save_quote(quote_data):
    """
    Saves a quote to Firestore.
    Returns the ID of the new quote, or None on error.
    """
    db_client = get_db()
    if not db_client:
        print("Firestore database not initialized.")
        return None

    try:
        # Generate a unique ID for the quote
        quote_id = str(uuid.uuid4())
        quote_data["id"] = quote_id
        
        # Set the document in the 'quotes' collection
        db_client.collection('quotes').document(quote_id).set(quote_data)
        
        return quote_id
    except Exception as e:
        print(f"Error saving quote to Firestore: {e}")
        return None

def list_quotes():
    """
    Retrieves all quotes from Firestore.
    Returns a list of quotes, or None on error.
    """
    db_client = get_db()
    if not db_client:
        print("Firestore database not initialized.")
        return None

    try:
        quotes_ref = db_client.collection('quotes').stream()
        quotes = [quote.to_dict() for quote in quotes_ref]
        return quotes
    except Exception as e:
        print(f"Error listing quotes from Firestore: {e}")
        return None

def get_quote_by_id(quote_id):
    """
    Retrieves a single quote from Firestore by its full or partial ID.
    Returns the quote data, or None if not found or on error.
    """
    db_client = get_db()
    if not db_client:
        print("Firestore database not initialized.")
        return None

    try:
        # Query for documents where the ID starts with the given partial ID
        quotes_ref = db_client.collection('quotes').where('id', '>=', quote_id).where('id', '<=', quote_id + u'\uf8ff').stream()
        
        found_quotes = [quote.to_dict() for quote in quotes_ref]
        
        if len(found_quotes) == 1:
            return found_quotes[0]
        elif len(found_quotes) > 1:
            # Handle multiple matches if necessary (e.g., return a list or an error)
            return found_quotes # Or you could return an error indicating ambiguity
        else:
            return None # No quote found

    except Exception as e:
        print(f"Error getting quote from Firestore: {e}")
        return None

def update_quote_status(quote_id, new_status):
    """
    Updates the status of a quote in Firestore.
    Returns True on success, False on error, or "Ambiguous" if multiple matches.
    """
    db_client = get_db()
    if not db_client:
        print("Firestore database not initialized.")
        return False

    try:
        # First, find the document with the matching full or partial ID
        quotes_ref = db_client.collection('quotes').where('id', '>=', quote_id).where('id', '<=', quote_id + u'\uf8ff').stream()
        
        found_quotes = [q for q in quotes_ref]

        if len(found_quotes) == 1:
            quote_doc = found_quotes[0]
            # Update the status
            doc_ref = db_client.collection('quotes').document(quote_doc.id) # Use .id to get the document ID
            doc_ref.update({"status": new_status})
            return True
        elif len(found_quotes) > 1:
            print("Ambiguous quote ID.")
            return "Ambiguous" # Special return to indicate ambiguity
        else:
            return "Not Found"

    except Exception as e:
        print(f"Error updating quote status in Firestore: {e}")
        return False

def delete_quote(quote_id):
    """
    Deletes a quote from Firestore.
    Returns True on success, False on error, or "Ambiguous" if multiple matches.
    """
    db_client = get_db()
    if not db_client:
        print("Firestore database not initialized.")
        return False

    try:
        # First, find the document with the matching full or partial ID
        quotes_ref = db_client.collection('quotes').where('id', '>=', quote_id).where('id', '<=', quote_id + u'\uf8ff').stream()
        
        found_quotes = [q for q in quotes_ref]

        if len(found_quotes) == 1:
            quote_doc = found_quotes[0]
            db_client.collection('quotes').document(quote_doc.id).delete() # Use .id to get the document ID
            return True
        elif len(found_quotes) > 1:
            print("Ambiguous quote ID.")
            return "Ambiguous" # Special return to indicate ambiguity
        else:
            return "Not Found"

    except Exception as e:
        print(f"Error deleting quote from Firestore: {e}")
        return False

def update_quote(quote_id, quote_data):
    """
    Updates a quote in Firestore.
    Returns True on success, False on error.
    """
    db_client = get_db()
    if not db_client:
        print("Firestore database not initialized.")
        return False

    try:
        # Use .update() for partial updates
        db_client.collection('quotes').document(quote_id).update(quote_data)
        return True
    except Exception as e:
        print(f"Error updating quote in Firestore: {e}")
        return False