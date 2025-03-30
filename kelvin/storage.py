import gzip
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from django.core.files.base import ContentFile
from django.utils.deconstruct import deconstructible


@deconstructible
class GzipStaticFilesStorage(ManifestStaticFilesStorage):
    """
    A storage backend that automatically creates .gz versions of static files.
    Only compresses JS and CSS files.
    """

    def _save(self, name, content):
        """
        Save the file and create a .gz version if it's a JS or CSS file.
        """
        # Save the original file
        path = super()._save(name, content)

        # Only compress JS and CSS files
        if path.endswith((".js", ".css")):
            # Create the .gz version
            gz_path = f"{path}.gz"
            if not self.exists(gz_path):
                # Read the original file content
                original_content = self.open(path).read()

                # Create gzipped content
                gzipped_content = gzip.compress(original_content)

                # Save the gzipped version
                self._save(gz_path, ContentFile(gzipped_content))

        return path
