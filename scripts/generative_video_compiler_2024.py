"""
Generative Video Compiler — 2024 original
=========================================

THIS IS THE SCRIPT THAT MADE *TAKEN PICTURES*. It is preserved exactly as it
ran, including its bugs, because it is the historical record of the piece.

Reading it back in 2026 showed it never did several things the design document
specified: the random blend modes and opacities were assigned but never applied
(every layer composited with `multiply` at full strength), the InceptionV3
recognition pass loaded the model but never called predict(), and no video was
compiled. See README.md, and `generative_video_compiler_2026.py` for a working
revision.

Do not "fix" this file. Its errors are the reason the film looks the way it does.
"""

import os
import random
import tensorflow as tf
import cv2
import numpy as np
import subprocess
from datetime import datetime
from PIL import Image, ImageEnhance, ImageFilter
from PIL import ImageChops
import shutil
import re
# Additional imports may be required such as OpenCV, TensorFlow, FFmpeg, etc.
from tensorflow.keras.applications.inception_v3 import InceptionV3
from tensorflow.keras.applications.inception_v3 import preprocess_input
from tensorflow.keras.preprocessing import image as tf_image
from tqdm import tqdm

class GenerativeVideoCompiler:
    def __init__(self):
        self.video_frames_dir = '/Users/jefftownsend/Dropbox/arts/video/video_art/GenerativeVideoCompiler/github_repository/data'
        self.output_dir = '/Users/jefftownsend/Dropbox/arts/video/video_art/GenerativeVideoCompiler/github_repository/output'
        self.drawers = [[], [], []]  # Three drawers, each containing a list of containers
        self.total_frames = 360  # 12 frames per second for 30 seconds

    def fill_drawer(self, drawer):
        image_count = 0
        from tqdm import tqdm
        pbar = tqdm(total=self.total_frames, desc="Filling drawer")
        while image_count < self.total_frames:
            print("Creating container...")
            randomNumber = min(self.total_frames - image_count, random.randint(10, 75))
            container = {
                'randomNumber': randomNumber,
                'randomOpacity': random.uniform(0.3, 0.7),
                'randomBlendMode': random.choice(['multiply', 'screen', 'overlay', 'soft_light'])
            }
            print(f"Container created with randomNumber: {container['randomNumber']}, "
                  f"randomOpacity: {container['randomOpacity']}, "
                  f"randomBlendMode: {container['randomBlendMode']}")
            drawer.append(container)
            image_count += container['randomNumber']
            pbar.update(container['randomNumber'])
        pbar.close()

    def seek_and_fill(self, drawer):
        from tqdm import tqdm
        pbar = tqdm(total=len(drawer), desc="Seeking and filling containers")
        for drawer_index, current_drawer in enumerate(self.drawers):
            if current_drawer is drawer:
                drawer_dir = os.path.join(self.output_dir, f'drawer_{drawer_index + 1}')
                break
        os.makedirs(drawer_dir, exist_ok=True)
        image_sequence_number = 0
        for container_index, container in enumerate(drawer):
            image_count = container['randomNumber']
            available_images = sorted([img for img in os.listdir(self.video_frames_dir) if os.path.isfile(os.path.join(self.video_frames_dir, img)) and img.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))])
            if not available_images:
                raise Exception("No valid images found in the video_frames_dir.")
            container_dir = os.path.join(drawer_dir, f'container_{container_index + 1}')
            os.makedirs(container_dir, exist_ok=True)
            # Randomly select a starting index for image selection
            start_index = random.randint(0, len(available_images) - image_count)
            selected_images = available_images[start_index:start_index + image_count]
            for img in selected_images:
                src = os.path.join(self.video_frames_dir, img)
                dst = os.path.join(container_dir, f'{str(image_sequence_number).zfill(5)}.png')
                shutil.copy(src, dst)  # Copy the image to the container directory
                image_sequence_number += 1
            container['images'] = [os.path.join(container_dir, f'{str(i).zfill(5)}.png') for i in range(image_sequence_number - image_count, image_sequence_number)]
            print(f"Container {container_index + 1} filled with {len(container.get('images', []))} images.")
            if not available_images:
                continue
            pbar.update(1)
        pbar.close()

    def layer_and_blend_images(self, drawer):
        print("Starting layer_and_blend_images process...")
        blended_images_dir = os.path.join(self.output_dir, 'blended_images')
        os.makedirs(blended_images_dir, exist_ok=True)
        print(f"Blended images directory created at: {blended_images_dir}")
        for image_sequence_number in range(self.total_frames):
            print(f"Processing image {image_sequence_number + 1}/{self.total_frames}")
            blended_image = Image.new('RGBA', (128, 128), (0, 0, 0, 0))  # Assuming all images are the same size
            for drawer_index in range(len(self.drawers)):
                # Calculate the container index and image index within the container
                container_index = 0
                image_index_within_container = image_sequence_number
                while image_index_within_container >= len(self.drawers[drawer_index][container_index]['images']):
                    image_index_within_container -= len(self.drawers[drawer_index][container_index]['images'])
                    container_index += 1
                    if container_index >= len(self.drawers[drawer_index]):
                        # If we've run out of containers, use the last image of the last container
                        container_index = len(self.drawers[drawer_index]) - 1
                        image_index_within_container = len(self.drawers[drawer_index][container_index]['images']) - 1
                        break
                image_path = self.drawers[drawer_index][container_index]['images'][image_index_within_container]
                if not os.path.exists(image_path):
                    raise FileNotFoundError(f"File not found: {image_path}")
                image = Image.open(image_path).convert('RGBA')
                print(f"Opened image from path: {image_path}")
                if drawer_index == 0:
                    blended_image = image
                else:
                    # Apply blending with the previous image
                    blended_image = ImageChops.multiply(blended_image, image)
            # Save the blended image
            blended_image_path = os.path.join(blended_images_dir, f'bl{str(image_sequence_number).zfill(3)}.png')
            blended_image.save(blended_image_path, 'PNG')
            # Upscale the blended image using Upscayl
            print(f"Blended image saved to: {blended_image_path}")
        print("layer_and_blend_images process completed.")

    def apply_overlay(self, base, top, opacity):
        # This method implements the overlay blend mode
        # Convert images to numpy arrays
        base_array = np.array(base)
        top_array = np.array(top)
        # Normalize the arrays
        base_norm = base_array / 255.0
        top_norm = top_array / 255.0
        # Create an empty array for the output
        result = np.zeros(base_array.shape, dtype=np.float32)
        # Apply the overlay blend mode algorithm
        mask = base_norm <= 0.5
        result[mask] = (2 * base_norm[mask] * top_norm[mask])
        result[~mask] = (1 - 2 * (1 - base_norm[~mask]) * (1 - top_norm[~mask]))
        # Apply opacity
        result = (result * opacity + base_norm * (1 - opacity))
        # Convert the result to an image
        result_image = Image.fromarray((result * 255).astype(np.uint8))
        return result_image

    def analyze_images(self):
        print("Starting analyze_images process...")
        # Load the InceptionV3 model pre-trained on ImageNet data
        model = InceptionV3(weights='imagenet')
        blended_images_dir = os.path.join(self.output_dir, 'blended_images')

        for i in range(self.total_frames):
            img_path = os.path.join(blended_images_dir, f'bl{str(i).zfill(3)}.png')
            img = tf_image.load_img(img_path, target_size=(299, 299))
            x = tf_image.img_to_array(img)
            x = np.expand_dims(x, axis=0)
            x = preprocess_input(x)

            # Here you can further process the predictions as needed for your application
            # For example, you might want to store them, or use them to influence subsequent steps
        print("analyze_images process completed.")

    def interpolate_frames(self):
        print("Starting interpolate_frames process...")
        interpolated_frames_dir = os.path.join(self.output_dir, 'interpolated_frames')
        os.makedirs(interpolated_frames_dir, exist_ok=True)

        for i in range(self.total_frames - 1):
            frame1_path = os.path.join(self.output_dir, 'blended_images', f'bl{str(i).zfill(3)}.png')
            frame2_path = os.path.join(self.output_dir, 'blended_images', f'bl{str(i+1).zfill(3)}.png')
            frame1 = cv2.imread(frame1_path)
            frame2 = cv2.imread(frame2_path)

            # Convert frames to float for interpolation
            frame1_float = frame1.astype(np.float32)
            frame2_float = frame2.astype(np.float32)

            # Compute the interpolated frame
            alpha = 0.5
            interpolated_frame = cv2.addWeighted(frame1_float, 1-alpha, frame2_float, alpha, 0)
            interpolated_frame = interpolated_frame.astype(np.uint8)

            # Save the interpolated frame
            interpolated_frame_path = os.path.join(interpolated_frames_dir, f'frame_{str(i).zfill(3)}_interpolated.png')
            cv2.imwrite(interpolated_frame_path, interpolated_frame)

        # Handle the last frame if necessary by repeating the last blended image
        last_blended_frame_path = os.path.join(self.output_dir, 'blended_images', f'bl{str(self.total_frames - 1).zfill(3)}.png')
        if os.path.exists(last_blended_frame_path):
            last_blended_frame = cv2.imread(last_blended_frame_path)
            if last_blended_frame is not None:
                cv2.imwrite(os.path.join(interpolated_frames_dir, f'frame_{str(self.total_frames - 1).zfill(3)}_interpolated.png'), last_blended_frame)
            else:
                raise FileNotFoundError(f"Last blended frame not found: {last_blended_frame_path}")
        print("interpolate_frames process completed.")

    def compile_video(self):
        print("Starting compile_video process...")
        # timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # output_video_name = f'GenerativeVideoCompiler_Output_{timestamp}.mp4'
        interpolated_frames_dir = os.path.join(self.output_dir, 'interpolated_frames')
        blended_images_dir = os.path.join(self.output_dir, 'blended_images')
        # output_video_path = os.path.join(self.output_dir, 'compiled_videos', output_video_name)
        # os.makedirs(os.path.dirname(output_video_path), exist_ok=True)
        final_sequence_dir = os.path.join(self.output_dir, 'final_sequence')
        os.makedirs(final_sequence_dir, exist_ok=True)
        # Create a list of frame paths by alternating between blended and interpolated frames
        # Ensure that the frame paths are sorted numerically
        
        blended_frame_paths = sorted([
            os.path.join(blended_images_dir, f) for f in os.listdir(blended_images_dir)
            if f.endswith('.png')
        ], key=lambda x: int(re.search(r'(\d+)', os.path.basename(x)).group()))

        interpolated_frame_paths = sorted([
            os.path.join(interpolated_frames_dir, f) for f in os.listdir(interpolated_frames_dir)
            if f.endswith('.png') and 'interpolated' in f
        ], key=lambda x: int(re.search(r'(\d+)', os.path.basename(x)).group()))

        # Rename blended and interpolated frames to be sequential
        sequence_number = 1
        for frame_path in blended_frame_paths:
            new_frame_name = f'{str(sequence_number).zfill(5)}.png'
            new_frame_path = os.path.join(final_sequence_dir, new_frame_name)
            os.rename(frame_path, new_frame_path)
            sequence_number += 2  # Increment by 2 for the next blended image

        sequence_number = 2
        for frame_path in interpolated_frame_paths:
            new_frame_name = f'{str(sequence_number).zfill(5)}.png'
            new_frame_path = os.path.join(final_sequence_dir, new_frame_name)
            os.rename(frame_path, new_frame_path)
            sequence_number += 2  # Increment by 2 for the next interpolated image

        print(f'Blended and interpolated images have been moved to the final sequence directory:{final_sequence_dir}.')
        print("compile_video process completed.")

    def run(self):
        # Clear the output directory before starting the process
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        # This method orchestrates the entire process
        for drawer_index, drawer in enumerate(self.drawers):
            print(f"Creating and filling drawer {drawer_index + 1}...")
            self.fill_drawer(drawer)
            self.seek_and_fill(drawer)
            print(f"Drawer {drawer_index + 1} is now filled with images.")

        print("Starting the blending phase...")
        for drawer in self.drawers:
            self.layer_and_blend_images(drawer)
        print("Blending phase completed.")

        print("Starting the analysis phase...")
        self.analyze_images()
        print("Analysis phase completed.")

        print("Starting the interpolation phase...")
        self.interpolate_frames()
        print("Interpolation phase completed.")

        print("Starting the video compilation...")
        self.compile_video()
        print("Video compilation completed.")

        print("All steps completed. The video compilation is finished.")

        print("Starting the blending phase...")
        # The blending phase will be implemented here
        # self.layer_and_blend_images()
        # The rest of the processes after the blending phase will go here
        # self.analyze_images()
        # self.interpolate_frames()
        # self.compile_video()
        print("All steps completed. The video compilation is finished.")

if __name__ == '__main__':
    gvc = GenerativeVideoCompiler()
    gvc.run()