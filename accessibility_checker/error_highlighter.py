# accessibility_checker/error_highlighter.py
import cv2
import os
import re


def union_bounds(bounds1, bounds2):
    """Combina dois retângulos (tuplas de 4 inteiros) em um único retângulo que os engloba."""
    x1 = min(bounds1[0], bounds2[0])
    y1 = min(bounds1[1], bounds2[1])
    x2 = max(bounds1[2], bounds2[2])
    y2 = max(bounds1[3], bounds2[3])
    return x1, y1, x2, y2

class ErrorHighlighter:
    def __init__(self, image_path: str):
        self.original_image = cv2.imread(image_path)
        self.image_copies = {}
        self.error_colors = {
            'Contrast Failure': (255, 0, 0),
            'Missing Content Description': (0, 0, 255),
            'Non-essential Content Description': (255, 0, 255),
            'Link Purpose Failure': (0, 0, 255),
            'Missing Accessible Name': (128, 0, 128),
            'Missing State Information': (255, 165, 0),
            'Missing Error Description': (0, 0, 255),
            'Missing Label or Instruction': (0, 0, 255),
            'Focus Order Failure': (0, 0, 255),
            'Target Size Failure': (255, 0, 0),
            'Target Size Failure (Minimum)': (255, 0, 0),
        }

    def highlight_error(self, error_info: dict):
        error_type = error_info['type'].strip()
        bounds = error_info['bounds']
        # Se "bounds" for uma lista com dois bounds (ex.: sobreposição), combine-os:
        if isinstance(bounds, list) and len(bounds) == 2:
            bounds = union_bounds(bounds[0], bounds[1])
        # Agora, espere um 4-tuple:
        x1, y1, x2, y2 = bounds
        if error_type not in self.image_copies:
            self.image_copies[error_type] = self.original_image.copy()
        image_copy = self.image_copies[error_type]
        height, width, _ = self.original_image.shape
        x1 = max(0, min(x1, width - 1))
        x2 = max(0, min(x2, width - 1))
        y1 = max(0, min(y1, height - 1))
        y2 = max(0, min(y2, height - 1))
        color = self.error_colors.get(error_type, (0, 0, 0))
        thickness = 3
        cv2.rectangle(image_copy, (x1, y1), (x2, y2), color, thickness)
        cv2.putText(image_copy, error_type.replace('_', ' '), (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    def save_images(self, output_folder: str = "output_images"):
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        for error_type, image in self.image_copies.items():
            safe_error_type = re.sub(r'[<>:"/\\|?*]', '_', error_type)
            file_name = safe_error_type.replace(' ', '_') + ".png"
            output_path = os.path.join(output_folder, file_name)
            cv2.imwrite(output_path, image)
            print(f"Image saved at: {output_path}")
