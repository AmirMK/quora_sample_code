import os
import logging
from fastapi import FastAPI
import uvicorn
import fastapi_poe as fp
from typing import AsyncIterable
from io import BytesIO
from vertexai.preview.vision_models import ImageGenerationModel
import vertexai
import re  
from google.auth import load_credentials_from_file

# Set up logging to include INFO level messages
logging.basicConfig(level=logging.INFO)

# Retrieve environment variables
project_id = os.getenv("PROJECT_ID")
location = os.getenv("LOCATION")
poe_access_key = os.getenv("POE_ACCESS_KEY")
credentials, project = load_credentials_from_file('xxx.json')

# Validate required environment variables
if not project_id:
    raise ValueError("PROJECT_ID environment variable is not set.")
if not location:
    raise ValueError("LOCATION environment variable is not set.")
if not poe_access_key:
    raise ValueError("POE_ACCESS_KEY environment variable is not set.")

# Initialize Vertex AI
vertexai.init(project=project_id, location=location, credentials=credentials)

# Initialize the image generation model
image_model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")

app = FastAPI()

class ImageResponsePoeBot(fp.PoeBot):
    async def get_response(self, request: fp.QueryRequest) -> AsyncIterable[fp.PartialResponse]:
        try:
            # Log the full request payload
            logging.info(f"Full request payload: {request.dict()}")

            # Extract the last message content
            last_message = request.query[-1].content
            logging.info(f"Extracted prompt: {last_message}")

            if not last_message:
                yield fp.PartialResponse(text="Prompt is required")
                return

            # Default number of images
            number_of_images = 1

            # Check for the --number_of_images=n syntax in the prompt
            match = re.search(r"--number_of_images\s*=\s*(\d+)", last_message)

            if match:
                n = int(match.group(1))
                # Validate n according to the rules
                if n <= 0:
                    number_of_images = 1
                elif n > 4:
                    number_of_images = 4
                else:
                    number_of_images = n
                
                # Remove the --number_of_images=n part from the prompt
                last_message = re.sub(r"--number_of_images\s*=\s*\d+", "", last_message).strip()


            logging.info(f"Number of images set to: {number_of_images}")
            logging.info(f"Cleaned prompt: {last_message}")

            # Generate the images using the cleaned prompt
            logging.info("Generating images with Gemini...")
            images = image_model.generate_images(
                prompt=last_message,  # Use the cleaned prompt here
                number_of_images=number_of_images,
                language="en",
                aspect_ratio="1:1"
            )

            # Check if images were generated successfully
            if len([image for image in images]) == 0:
                yield fp.PartialResponse(text="No images were generated. Please modify your prompt or try again later.")
                return
                       
            for index, img_obj in enumerate(images):
                # Check if the image object has the _pil_image attribute
                if not hasattr(img_obj, '_pil_image'):
                    logging.warning(f"Image {index + 1} could not be generated. Skipping...")
                    continue

                # Convert the generated image to binary format
                generated_image = img_obj._pil_image
                image_bytes = BytesIO()
                generated_image.save(image_bytes, format='JPEG')
                image_bytes.seek(0)  # Reset the file pointer to the beginning
                
                # Create a filename based on the prompt (first 10 characters) and image index
                sanitized_prompt = last_message[:10].replace(" ", "_")
                filename = f"{sanitized_prompt}_image_{index + 1}.jpg"

                # Attach the binary image as a response attachment
                await self.post_message_attachment(
                    message_id=request.message_id,
                    file_data=image_bytes.getvalue(),
                    filename=filename
                )

            # Yield a response after all images have been attached
            yield fp.PartialResponse(text=f'{number_of_images} image(s) generated by Imagen3 attached for "{last_message}".')

        except Exception as e:
            logging.error(f"Error processing the request: {e}")
            yield fp.PartialResponse(text=f"Error: {e}")

# Set up the Poe bot with the required access key
poe_bot = ImageResponsePoeBot()
app = fp.make_app(poe_bot, access_key=poe_access_key)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
