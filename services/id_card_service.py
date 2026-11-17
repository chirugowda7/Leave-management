import io
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
from flask import current_app

def generate_id_card_image(emp, side='front'):
    if emp and not isinstance(emp, dict):
        emp = dict(emp)
    elif not emp:
        emp = {}

    static_folder = current_app.static_folder

    if side == 'front':
        bg_path = os.path.join(static_folder, 'images', 'id_card_front_clean.jpg')
        card = Image.open(bg_path).convert('RGBA')

        photo_path = None
        if emp.get('profile_pic'):
            possible_path = os.path.join(static_folder, 'uploads', 'profile_pics', emp['profile_pic'])
            if os.path.exists(possible_path):
                photo_path = possible_path

        if photo_path:
            try:
                user_photo = Image.open(photo_path).convert('RGBA')
            except Exception:
                user_photo = None
        else:
            user_photo = None

        if user_photo:
            user_photo = user_photo.resize((255, 258), Image.Resampling.LANCZOS)
        else:
            user_photo = Image.new('RGBA', (255, 258), (30, 41, 59, 255))
            d = ImageDraw.Draw(user_photo)
            initial = (emp.get('full_name') or 'E')[0].upper()
            try:
                font_lg = ImageFont.truetype("arialbd.ttf", 110)
            except Exception:
                try:
                    font_lg = ImageFont.truetype("arial.ttf", 110)
                except Exception:
                    font_lg = ImageFont.load_default()
            d.text((127, 129), initial, fill=(255, 255, 255), anchor="mm", font=font_lg)

        # Paste photo at exact inner gold frame position (200, 194)
        card.paste(user_photo, (200, 194))

        draw = ImageDraw.Draw(card)

        # Base font loading helper
        def get_font(size):
            try:
                return ImageFont.truetype("arialbd.ttf", size)
            except Exception:
                try:
                    return ImageFont.truetype("arial.ttf", size)
                except Exception:
                    return ImageFont.load_default()

        # Name formatting & auto-scaling
        name_str = (emp.get('full_name') or '').upper()
        title_size = 26
        if len(name_str) > 22:
            title_size = 20
        elif len(name_str) > 18:
            title_size = 22
        font_title = get_font(title_size)

        draw.text((328, 487), name_str, fill=(255, 255, 255), anchor="mm", font=font_title)

        emp_id = emp.get('emp_id') or ''
        blood_group = emp.get('blood_group') or 'O +ve'
        email = emp.get('email') or ''
        phone = emp.get('phone') or '9148765643'
        address = emp.get('address') or 'Hubli'

        # Clean background in label area to clear any pre-existing truncated background text
        bg_blue = (15, 122, 204, 255)
        draw.rectangle([(40, 525), (255, 790)], fill=bg_blue)

        font_lbl = get_font(23)
        font_val = get_font(23)

        fields = [
            ('Employee ID', emp_id, 544),
            ('Blood Group', blood_group, 593),
            ('Email ID', email, 638),
            ('Contact No', phone, 708),
            ('Address', address, 758),
        ]

        for label, val, y in fields:
            # Draw label aligned on left at x=60
            draw.text((60, y), label, fill=(255, 255, 255), font=font_lbl)
            # Draw colon aligned at x=245
            draw.text((245, y), ':', fill=(255, 255, 255), font=font_lbl)
            
            # Auto scale font for values if needed
            val_font = font_val
            val_str = str(val or '')
            if label == 'Email ID':
                if len(val_str) > 28:
                    val_font = get_font(15)
                elif len(val_str) > 22:
                    val_font = get_font(17)
                elif len(val_str) > 18:
                    val_font = get_font(20)
            elif len(val_str) > 24:
                val_font = get_font(18)

            # Draw value directly beside colon at x=265
            draw.text((265, y), val_str, fill=(255, 255, 255), font=val_font)

        output = io.BytesIO()
        card.convert('RGB').save(output, format='JPEG', quality=95)
        output.seek(0)
        return output
    else:
        bg_path = os.path.join(static_folder, 'images', 'id_card_back_template.jpg')
        if not os.path.exists(bg_path):
            bg_path = os.path.join(static_folder, 'images', 'id_card_back_clean.jpg')
            
        card = Image.open(bg_path).convert('RGBA')

        output = io.BytesIO()
        card.convert('RGB').save(output, format='JPEG', quality=95)
        output.seek(0)
        return output
