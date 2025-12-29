import asyncio
import aiohttp
import os

from dotenv import load_dotenv


# Test configuration
BASE_URL = "http://localhost:8000"  # Adjust if your API runs on different port
GUILD_ID = 1210097999699779594  # Replace with a test guild ID
TEST_IMAGE_PATH = "image.jpg"  # Path to your test image file
load_dotenv()

headers = {
    "Plana-API-Key": os.getenv("PLANA_API_KEY"),
}


async def test_upload_image():
    """Test uploading an image to the guild images endpoint."""

    # Check if test image exists
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f"❌ Test image not found: {TEST_IMAGE_PATH}")
        print("Please create a test image file or update TEST_IMAGE_PATH")
        return

    url = f"{BASE_URL}/api/guilds/{GUILD_ID}/images"

    async with aiohttp.ClientSession() as session:
        try:
            # Read the image file
            with open(TEST_IMAGE_PATH, "rb") as f:
                # Create multipart form data
                data = aiohttp.FormData()
                data.add_field(
                    "file",
                    f,
                    filename=os.path.basename(TEST_IMAGE_PATH),
                    content_type="image/jpeg",
                )

                print(f"🚀 Uploading image to: {url}")
                print(f"📁 File: {TEST_IMAGE_PATH}")

                # Make the POST request
                async with session.post(url, data=data, headers=headers) as response:
                    response_data = await response.json()

                    print(f"📊 Status Code: {response.status}")
                    print(f"📋 Response: {response_data}")

                    if response.status == 201:
                        print("✅ Image uploaded successfully!")
                        if "data" in response_data and "url" in response_data["data"]:
                            print(f"🔗 Image URL: {response_data['data']['url']}")
                    else:
                        print("❌ Upload failed!")

        except aiohttp.ClientError as e:
            print(f"❌ Network error: {e}")
        except FileNotFoundError:
            print(f"❌ Test image file not found: {TEST_IMAGE_PATH}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")


async def main():
    """Main test function."""
    print("🧪 Starting S3 Image Upload Tests")
    print("=" * 50)

    # Test image upload
    print("\n2️⃣ Testing Image Upload:")
    await test_upload_image()

    print("\n🏁 Tests completed!")


if __name__ == "__main__":
    # Run the async tests
    asyncio.run(main())
