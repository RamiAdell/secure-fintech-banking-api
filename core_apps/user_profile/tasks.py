import base64
from uuid import UUID

import cloudinary.uploader
from celery import shared_task
from django.apps import apps
from django.core.files.storage import default_storage
from loguru import logger


@shared_task(name="upload_photos_to_cloudinary")
def upload_photos_to_cloudinary(profile_id: UUID, photos: dict) -> None:
    try:
        profile_model = apps.get_model("user_profile", "Profile")
        profile = profile_model.objects.get(id=profile_id)

        for field_name, photo_data in photos.items():
            if photo_data["type"] == "base64":
                image_content = base64.b64decode(photo_data["data"])
                response = cloudinary.uploader.upload(image_content)
            else:
                with open(photo_data["data"], "rb") as image_file:
                    response = cloudinary.uploader.upload(image_file)
                default_storage.delete(photo_data["path"])
            setattr(profile, field_name, response["public_id"])
            setattr(profile, f"{field_name}_url", response["url"])
        profile.save()

        logger.info(f"Photos for  {profile.user.email}'s uploaded successfully")

    except Exception as e:
        logger.error(f"Failed to upload photos for profile {profile_id}: {str(e)} ")

        for photo_data in photos.values():
            if photo_data["type"] == "file" and default_storage.exists(
                photo_data["path"]
            ):
                default_storage.delete(photo_data["path"])