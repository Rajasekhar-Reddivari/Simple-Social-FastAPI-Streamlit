from fastapi import FastAPI , HTTPException, File, UploadFile, Form, Depends
from app.schemas import PostCreate, PostResponse , UserCreate, UserUpdate,UserRead
from app.db import Post, create_db_and_tables, get_async_session, User
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.images import imagekit
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions

from starlette.concurrency import run_in_threadpool

import shutil
import os
import uuid
import tempfile
import requests
from app.users import fastapi_users, auth_backend,current_active_user
@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield
app = FastAPI(lifespan=lifespan)

app.include_router(fastapi_users.get_auth_router(auth_backend),prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate),prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(),prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead),prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate),prefix="/users", tags=["users"])

@app.post("/upload")
async def upload(
        file: UploadFile = File(...),
        caption: str = Form(...),
        user: User= Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    temp_file_path = None
    try:
        # Save uploaded file to a temporary file (preserve extension)
        _, ext = os.path.splitext(file.filename)
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file , temp_file)

        # Upload is blocking (uses requests); run in threadpool to avoid blocking the event loop
        def do_upload(path, fname, content_type):
            with open(path, "rb") as f:
                return imagekit.upload_file(
                    file=f,
                    file_name=fname,
                    options=UploadFileRequestOptions(
                        use_unique_file_name=True,
                        tags=["backend-upload"]
                    )
                )

        try:
            upload_result = await run_in_threadpool(do_upload, temp_file_path, file.filename, file.content_type)
        except requests.exceptions.SSLError as e:
            # Surface SSL errors with a clearer message for debugging
            raise HTTPException(status_code=502, detail=f"SSL error when uploading to ImageKit: {e}")

        # Collect debug information about upload_result to help diagnose SDK behavior
        debug_info = {
            "type": type(upload_result).__name__,
            "repr": repr(upload_result)
        }
        # Try to include __dict__ if available
        try:
            debug_info["dict"] = getattr(upload_result, "__dict__", None)
        except Exception:
            debug_info["dict"] = None

        # Extract response-like information if present
        response_obj = getattr(upload_result, "response", None)
        response_info = None
        if response_obj is not None:
            # try common attributes
            response_info = {
                "http_status_code": getattr(response_obj, "http_status_code", None),
                "status_code": getattr(response_obj, "status_code", None),
                "text": getattr(response_obj, "text", None)
            }
        debug_info["response"] = response_info

        # The SDK can return either an object with attributes or a dict; handle both safely
        # Prefer success detection by presence of a URL returned by the SDK
        url = None
        name = None
        if isinstance(upload_result, dict):
            url = upload_result.get("url") or upload_result.get("filePath")
            name = upload_result.get("name")
        else:
            # object-like
            url = getattr(upload_result, "url", None)
            name = getattr(upload_result, "name", None)

        # Consider upload successful when we received a non-empty URL
        if url:
            # try to get file_id if SDK returned it
            file_id = None
            if isinstance(upload_result, dict):
                file_id = upload_result.get("file_id") or upload_result.get("fileId") or upload_result.get("fileId")
            else:
                file_id = getattr(upload_result, "file_id", None) or getattr(upload_result, "fileId", None) or getattr(upload_result, "fileId", None)

            post = Post(
                user_id = user.id,
                caption=caption,
                url=url,
                file_type="video" if file.content_type.startswith("video/") else "image",
                file_name=name or file.filename,
                file_id=file_id
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)
            return post
        else:
            # Provide more info in the error response to aid debugging
            raise HTTPException(status_code=502, detail={
                "message": "ImageKit upload failed",
                "upload_result_type": type(upload_result).__name__,
                "upload_result": str(upload_result),
                "debug": debug_info
            })

    except HTTPException:
        # re-raise HTTPExceptions unchanged
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
        try:
            file.file.close()
        except Exception:
            pass

@app.get("/feed")
async def get_feed(
        session: AsyncSession = Depends(get_async_session),
        user: User= Depends(current_active_user)
):
    result = await session.execute(select(Post).order_by(Post.created_at.desc()))
    posts = [row[0] for row in result.all()]

    result = await session.execute(select(User))
    users = [row[0] for row in result.all()]
    # Map user id -> email (string) to avoid returning whole user objects to client
    user_dict = {u.id: getattr(u, 'email', 'unknown') for u in users}

    posts_data =[]
    for post in posts:
        posts_data.append(
            {
                "id": str(post.id),
                "user_id" : str(post.user_id),
                "caption" : post.caption,
                "url" : post.url,
                "file_type" : post.file_type,
                "file_name" : post.file_name,
                "created_at" : post.created_at.isoformat(),
                "is_owner": post.user_id == user.id,
                "email": user_dict.get(post.user_id , "unknown")
            }
        )
    return {"posts": posts_data}
@app.delete("/posts/{post_id}")
async def delete_post(
        post_id: str,
        session: AsyncSession = Depends(get_async_session),
        user: User= Depends(current_active_user)
):
    try:
        post_uuid = uuid.UUID(post_id)
        result = await session.execute(select(Post).where(Post.id == post_uuid))
        post = result.scalars().first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        if post.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this post")

        # If we have a file_id saved, attempt to delete from ImageKit first
        file_id = getattr(post, "file_id", None)
        if file_id:
            def do_delete(fid):
                try:
                    return imagekit.delete_file(fid)
                except Exception as e:
                    # return exception for logging
                    return e

            delete_result = await run_in_threadpool(do_delete, file_id)
            # If delete_result is an exception, log it (here we include in the response)
            if isinstance(delete_result, Exception):
                # proceed with DB delete but inform user that remote delete failed
                await session.delete(post)
                await session.commit()
                return {"success": True, "message": "Post deleted from DB; failed to delete file from ImageKit", "imagekit_delete_error": str(delete_result)}

        await session.delete(post)
        await session.commit()
        return {"success": True , "message": "Post deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))






