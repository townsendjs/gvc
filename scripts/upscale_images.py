import os
import glob
import torch
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer
from PIL import Image
import numpy as np

class ImageUpscaler:
    def __init__(self, input_dir, output_dir, scale=4):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.scale = scale
        self.model_path = '/Users/jefftownsend/Real-ESRGAN-master/experiments/pretrained_models/RealESRGAN_x4plus.pth'  # Update this path to the correct location of the model file

    def setup_model(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.upscale_model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=self.scale)
        self.upscale_model.load_state_dict(torch.load(self.model_path), strict=False)
        self.upscale_model.eval()
        self.upscale_model = self.upscale_model.to(self.device)

        self.upscale_service = RealESRGANer(
            scale=self.scale,
            model_path=self.model_path,
            model=self.upscale_model,
            tile=0,
            tile_pad=10,
            pre_pad=0,
            half=True
        )

    def upscale_images(self):
        os.makedirs(self.output_dir, exist_ok=True)
        image_paths = glob.glob(os.path.join(self.input_dir, '*.png'))
        for image_path in image_paths:
            img_name = os.path.basename(image_path)
            output_path = os.path.join(self.output_dir, img_name)
            img = Image.open(image_path).convert('RGB')
            img = np.array(img)  # Convert PIL Image to NumPy array

            # Upscale the image
            # Ensure the image is in float32 before upscaling
            img_float32 = img.astype(np.float32) / 255.0  # Normalize the image to [0, 1]
            # Convert the image to a tensor and unsqueeze to add the batch dimension
            img_tensor = torch.from_numpy(img_float32).to(self.device).unsqueeze(0).permute(0, 3, 1, 2)
            # Cast the tensor to half precision if the model is in half precision
            if self.upscale_service.half:
                img_tensor = img_tensor.half()
            # Convert the image to a tensor and unsqueeze to add the batch dimension
            # Perform the upscaling
            with torch.no_grad():
                output_tensor = self.upscale_model(img_tensor)  # Keep the tensor in full precision
            # Convert the tensor back to an image
            output = output_tensor.squeeze().permute(1, 2, 0).cpu().numpy()
            output = (output * 255.0).clip(0, 255).astype(np.uint8)  # Denormalize and convert to uint8
            output = Image.fromarray(output)
            output.save(output_path)
            print(f'Upscaled image saved to: {output_path}')

if __name__ == '__main__':
    input_directory = '/Users/jefftownsend/Dropbox/arts/video/video_art/GenerativeVideoCompiler/github_repository/comp_and_up/compilled_frames'
    output_directory = '/Users/jefftownsend/Dropbox/arts/video/video_art/GenerativeVideoCompiler/github_repository/comp_and_up/upscaled_frames'
    upscaler = ImageUpscaler(input_directory, output_directory)
    upscaler.setup_model()
    upscaler.upscale_images()
