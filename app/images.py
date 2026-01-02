from imagekitio import ImageKit
import os
from dotenv import load_dotenv

load_dotenv()

# SDK initialization - prefer environment variables over hard-coded secrets
PRIVATE_KEY = os.getenv('IMAGEKIT_PRIVATE_KEY', 'private_xhO+8yY40R******************')
PUBLIC_KEY = os.getenv('IMAGEKIT_PUBLIC_KEY', 'public_YxE8rpcX2zHQe7ZekAbfodem/iQ=')
URL_ENDPOINT = os.getenv('IMAGEKIT_URL_ENDPOINT', 'https://ik.imagekit.io/axfrnzhvhe')

imagekit = ImageKit(
    private_key=PRIVATE_KEY,
    public_key=PUBLIC_KEY,
    url_endpoint=URL_ENDPOINT
)
