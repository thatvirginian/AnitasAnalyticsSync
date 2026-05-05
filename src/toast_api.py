# -*- coding: utf-8 -*-

import time
import requests
from sqlalchemy.dialects.postgresql import insert
from src.utils import get_env

# This pulls the engine and session factory from your setup file
# Adjust the import path if your file structure differs (e.g., if not in 'src')
from src.database_setup import SessionLocal, APIToken


class ToastAPI:
    def __init__(self):
        # Load configuration from environment (.env or Azure settings)
        self.base_url = get_env("TOAST_API_HOST")
        self.client_id = get_env("TOAST_CLIENT_ID")
        self.client_secret = get_env("TOAST_CLIENT_SECRET")

        self.token = None
        self.token_expiry = 0

        # Load cached token from Database immediately on initialization
        self._load_token_from_db()

    def _load_token_from_db(self):
        """Self-contained session to fetch token metadata from Postgres."""
        session = SessionLocal()
        try:
            # Query the api_tokens table for the 'toast' record
            token_record = session.query(APIToken).filter_by(service_name='toast').first()
            if token_record:
                self.token = token_record.access_token
                self.token_expiry = token_record.expires_at
        except Exception as e:
            print(f"Warning: Failed to read token from database: {e}")
        finally:
            session.close()

    def _save_token_to_db(self, created_at):
        """Atomic Upsert to ensure the token is updated in the database."""
        session = SessionLocal()
        try:
            # Prepare the Postgres-specific UPSERT (On Conflict Update)
            stmt = insert(APIToken).values(
                service_name='toast',
                access_token=self.token,
                client_id=self.client_id,
                expires_at=self.token_expiry,
                created_at=created_at
            )

            # If 'toast' exists, update the token and expiry
            stmt = stmt.on_conflict_do_update(
                index_elements=['service_name'],
                set_={
                    'access_token': stmt.excluded.access_token,
                    'expires_at': stmt.excluded.expires_at,
                    'created_at': stmt.excluded.created_at
                }
            )

            session.execute(stmt)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error: Failed to save token to database: {e}")
        finally:
            session.close()

    def _authenticate(self):
        """Fetch a fresh access token from the Toast Auth API."""
        print("Authenticating with Toast API (Refresh required)...")

        url = f"{self.base_url}/authentication/v1/authentication/login"
        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "userAccessType": "TOAST_MACHINE_CLIENT"
        }

        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        token_data = data.get("token", {})
        self.token = token_data.get("accessToken")
        expires_in = token_data.get("expiresIn", 86400)  # Default to 24h if missing

        if not self.token:
            raise Exception("No access token returned from Toast API.")

        # Save expiry time with a 1-hour safety buffer
        # This protects long-running order syncs across all Anita's locations
        now = time.time()
        self.token_expiry = now + expires_in - 3600

        # Sync the new token back to the shared database
        self._save_token_to_db(created_at=now)

        print("Token refreshed and saved to Database.")
        return self.token

    def get_token(self):
        """Return a valid token, checking the database/API only if expired."""
        if not self.token or time.time() >= self.token_expiry:
            return self._authenticate()
        return self.token

    def get_headers(self):
        """
        Standard header method used by fetch_all_bulk_orders.
        Kept identical to original version for project compatibility.
        """
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Content-Type": "application/json"
        }