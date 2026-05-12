from rembg import remove
from PIL import Image
import io

TAILLE = 512

def preprocess_image(image_bytes: bytes) -> Image.Image:
    # 1. Suppression du fond (le plus lourd)
    no_bg = remove(image_bytes)

    # 2. Ouverture et conversion en RGB (obligatoire pour CLIP)
    image = Image.open(io.BytesIO(no_bg)).convert("RGBA")
    
    # On crée un fond blanc pour remplacer la transparence de rembg
    final = Image.new("RGBA", image.size, (255, 255, 255))
    final.paste(image, (0, 0), image)
    image = final.convert("RGB")

    # 3. Crop automatique (enlève les marges vides après rembg)
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)

    # 4. Resize intelligent (maintient le ratio)
    image.thumbnail((TAILLE, TAILLE))

    # 5. Création du carré final 512x512
    new_img = Image.new("RGB", (TAILLE, TAILLE), (255, 255, 255))
    x = (TAILLE - image.width) // 2
    y = (TAILLE - image.height) // 2
    new_img.paste(image, (x, y))

    return new_img