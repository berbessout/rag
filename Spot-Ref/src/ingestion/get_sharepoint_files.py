import os
import urllib.parse
from typing import List, Optional
from io import BytesIO
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.user_credential import UserCredential
from office365.sharepoint.files.file import File
from urllib.parse import urlparse


class SharePoint:
    def __init__(self):
        """Initialize SharePoint client with credentials from environment variables."""
        # Load environment variables
        site_url = os.getenv('SHAREPOINT_SITE_URL')
        username = os.getenv('SHAREPOINT_USERNAME')
        password = os.getenv('SHAREPOINT_PASSWORD')
        library_name = os.getenv('SHAREPOINT_LIBRARY_NAME')

        # Validate environment variables
        missing_vars = []
        if not site_url:
            missing_vars.append("SHAREPOINT_SITE_URL")
        if not username:
            missing_vars.append("SHAREPOINT_USERNAME")
        if not password:
            missing_vars.append("SHAREPOINT_PASSWORD")
        if not library_name:
            missing_vars.append("SHAREPOINT_LIBRARY_NAME")
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        self.site_url = site_url
        self.username = username
        self.password = password
        self.library_name = library_name
        
        # Authenticate immediately and store the context
        try:
            self.ctx = ClientContext(self.site_url).with_credentials(
                UserCredential(self.username, self.password)
            )
            # Get the web context to determine the correct base path
            web = self.ctx.web
            self.ctx.load(web)
            self.ctx.execute_query()
            
            # For personal sites, the path starts with /personal/username
            if '-my.sharepoint' in self.site_url:
                parts = self.site_url.split('/personal/')
                if len(parts) < 2 or not parts[1]:
                    raise ValueError("Invalid personal SharePoint URL format. Expected '/personal/username' in the URL.")
                self.base_path = f"/personal/{parts[1]}/Documents"
            else:
                # For team sites, extract the path from the URL
                from urllib.parse import urlparse
                parsed = urlparse(self.site_url)
                self.base_path = parsed.path if parsed.path else web.server_relative_path
            
            print(f"Connected to SharePoint site at: {self.base_path}")
            
        except Exception as e:
            if "401" in str(e) or "Unauthorized" in str(e):
                raise ValueError("Authentication failed. Please check your credentials.")
            elif "404" in str(e):
                raise Exception("SharePoint site not found. Please check the site URL.")
            else:
                raise Exception(f"Failed to connect to SharePoint: {str(e)}")

    def list_ppt_files(self, folder_path: Optional[str] = None) -> List[str]:
        """List all PPT and PPTX files in a SharePoint document library or folder."""
        try:
            # For team sites, use the library name directly with proper formatting
            if folder_path:
                if self.base_path and self.base_path != '/':
                    folder_url = f"{self.base_path}/{self.library_name}/{folder_path.strip('/')}"
                else:
                    folder_url = f"/{self.library_name}/{folder_path.strip('/')}"
            else:
                if self.base_path and self.base_path != '/':
                    folder_url = f"{self.base_path}/{self.library_name}"
                else:
                    folder_url = f"/{self.library_name}"
            
            print(f"Accessing folder: {folder_url}")  # Debug info
            folder = self.ctx.web.get_folder_by_server_relative_url(folder_url)
            files = folder.files.get().execute_query()
            return [f.serverRelativeUrl for f in files if f.name.lower().endswith((".ppt", ".pptx"))]
        except Exception as e:
            print(f"[ERROR] Failed to access library. Error: {str(e)}")
            return []

    def download_file(self, server_relative_url: str, local_path: str = None) -> Optional[BytesIO]:
        """Download a file from SharePoint to either a local path or BytesIO object."""
        try:
            response = File.open_binary(self.ctx, server_relative_url)
            
            if local_path:
                with open(local_path, "wb") as local_file:
                    local_file.write(response.content)
                return None
            else:
                return BytesIO(response.content)
        except Exception as e:
            print(f"[ERROR] Failed to download file : {e}")
            raise

    def download_all_ppt_files(self, folder_path: Optional[str] = None, local_dir: Optional[str] = None) -> List[tuple[str, BytesIO]]:
        """Download all PPT/PPTX files from a SharePoint library/folder in a temporary folder."""
        ppt_files = self.list_ppt_files(folder_path)
        if not ppt_files:
            return []

        results = []
        for server_url in ppt_files:
            filename = os.path.basename(server_url)
            try:
                if local_dir:
                    local_path = os.path.join(local_dir, filename)
                    self.download_file(server_url, local_path)
                else:
                    file_bytes = self.download_file(server_url)
                    results.append((filename, file_bytes))
            except Exception as e:
                print(f"[ERROR] Failed to download '{filename} : {e}'")
                continue
        return results

    def get_file_web_url(self, server_relative_url: str, file_name: str) -> Optional[str]:
        """
        Get the web URL for a file that opens in the browser/office app.

        Args:
            server_relative_url (str): Server relative URL of the file
            file_name (str): Name of the file

        Returns:
            Optional[str]: SharePoint web URL for the file, or None if error occurs
        """
        try:
            file_obj = self.ctx.web.get_file_by_server_relative_url(server_relative_url)
            self.ctx.load(file_obj, ["UniqueId", "ServerRelativeUrl", "Name"])
            self.ctx.execute_query()

            unique_id = file_obj.properties["UniqueId"]
            file_url_encoded = urllib.parse.quote(file_name)
            
            parsed = urlparse(self.site_url)
            site_root = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            
            share_url = (
                f"{site_root}/_layouts/15/Doc.aspx"
                f"?sourcedoc=%7B{unique_id}%7D"
                f"&file={file_url_encoded}"
                f"&action=edit&mobileredirect=true"
            )
            return share_url

        except Exception as e:
            print(f"[ERROR] Failed to get web URL for file '{file_name}': {str(e)}")
            return None
