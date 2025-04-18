import os
import cv2
import time
import numpy as np
import urllib.request
import torch
from PIL import Image
import base64
from io import BytesIO

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class YOLORecaptchaSolver:
    def __init__(self, model_name="yolov5s"):
        """
        YOLO modeli kullanan reCAPTCHA çözme sınıfı.
        
        Args:
            model_name: YOLO model adı
        """
        print("YOLO modeli yükleniyor...")
        
        # YOLOv5 modelini yükle
        self.model = torch.hub.load('ultralytics/yolov5', model_name)
        
        # Sınıf eşleştirmeleri
        self.class_mappings = {
            "traffic light": [9], # YOLO sınıf indeksi
            "bicycle": [1],
            "car": [2],
            "motorcycle": [3],
            "airplane": [4],
            "bus": [5],
            "train": [6],
            "truck": [7],
            "boat": [8],
            "fire hydrant": [10],
            "stop sign": [11],
            "parking meter": [12],
            "bench": [13],
            "bird": [14],
            "cat": [15],
            "dog": [16],
            "horse": [17],
            "sheep": [18],
            "cow": [19],
            "elephant": [20],
            "bear": [21],
            "zebra": [22],
            "giraffe": [23]
        }
        
        print("YOLO modeli hazır!")
    
    def preprocess_image(self, image_data):
        """Görüntüyü model için hazırlar."""
        if isinstance(image_data, str) and image_data.startswith("data:image"):
            # Base64 kodlu görüntü
            base64_data = image_data.split(",")[1]
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(BytesIO(image_bytes))
        elif isinstance(image_data, str) and (image_data.startswith("http") or os.path.exists(image_data)):
            # URL veya dosya yolu
            if image_data.startswith("http"):
                with urllib.request.urlopen(image_data) as response:
                    image_bytes = response.read()
                image = Image.open(BytesIO(image_bytes))
            else:
                image = Image.open(image_data)
        else:
            # OpenCV görüntüsü
            if isinstance(image_data, np.ndarray):
                image = Image.fromarray(cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB))
        
        return image
    
    def detect_objects(self, image):
        """Görüntüdeki nesneleri algılar."""
        try:
            processed_image = self.preprocess_image(image)
            results = self.model(processed_image)
            
            # Algılanan nesneleri çıkar
            detections = []
            
            # predictions.pandas().xyxy[0]  # pandas tablosunu al
            for detection in results.xyxy[0].cpu().numpy():
                x1, y1, x2, y2, confidence, class_id = detection[:6]
                class_name = self.model.names[int(class_id)]
                
                detections.append({
                    "class": class_name,
                    "class_id": int(class_id),
                    "confidence": float(confidence),
                    "bbox": [int(x1), int(y1), int(x2), int(y2)]
                })
            
            return detections
        except Exception as e:
            print(f"Nesne algılama hatası: {e}")
            return []
    
    def matches_target(self, detections, target_object):
        """Algılanan nesnelerin hedef nesne ile eşleşip eşleşmediğini kontrol eder."""
        if not detections:
            return False
        
        target = target_object.lower()
        
        # YOLO class ID eşleştirmesi
        target_class_ids = []
        for object_name, ids in self.class_mappings.items():
            if object_name.lower() in target or target in object_name.lower():
                target_class_ids.extend(ids)
        
        # Eşleşme kontrolü
        for detection in detections:
            # Doğrudan sınıf adı eşleşmesi
            if target in detection["class"].lower() or detection["class"].lower() in target:
                if detection["confidence"] > 0.4:  # Minimum güven skoru
                    return True
            
            # Sınıf ID eşleşmesi
            if detection["class_id"] in target_class_ids and detection["confidence"] > 0.4:
                return True
        
        return False
    
    def extract_target_object(self, driver):
        """reCAPTCHA'nın hedef nesnesini çıkarır."""
        try:
            # reCAPTCHA iframe'ine geç
            iframe = driver.find_element(By.CSS_SELECTOR, "iframe[title='reCAPTCHA']")
            driver.switch_to.frame(iframe)
            
            # Checkbox'a tıkla
            checkbox = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "recaptcha-anchor"))
            )
            checkbox.click()
            
            # Ana frame'e geri dön
            driver.switch_to.default_content()
            
            # Challenge iframe'ine geç
            WebDriverWait(driver, 10).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe[title='recaptcha challenge expires in two minutes']"))
            )
            
            # Hedef nesne metnini al
            target_text = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".rc-imageselect-desc-wrapper"))
            ).text
            
            # "Select all images with X" formatından X'i çıkar
            target_object = target_text.split("with ")[-1].split(".")[0]
            print(f"Hedef nesne: {target_object}")
            
            return target_object
        except Exception as e:
            print(f"Hedef nesne çıkarma hatası: {e}")
            return None
    
    def extract_captcha_images(self, driver):
        """reCAPTCHA görüntülerini çıkarır."""
        try:
            images = []
            
            # Görüntü ızgarasını bul
            image_grid = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.rc-imageselect-table"))
            )
            
            # Tüm görüntü hücrelerini bul
            cells = image_grid.find_elements(By.CSS_SELECTOR, "td.rc-imageselect-tile")
            
            for i, cell in enumerate(cells):
                try:
                    # Hücredeki görüntüyü bul
                    img = cell.find_element(By.TAG_NAME, "img")
                    img_url = img.get_attribute("src")
                    
                    # Görüntüyü indir ve listele
                    with urllib.request.urlopen(img_url) as response:
                        img_data = response.read()
                        img_array = np.asarray(bytearray(img_data), dtype=np.uint8)
                        img_cv = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                        
                        images.append({
                            "index": i,
                            "element": cell,
                            "image": img_cv
                        })
                except Exception as e:
                    print(f"{i}. görüntü çıkarma hatası: {e}")
            
            return images
        except Exception as e:
            print(f"Captcha görüntüleri çıkarma hatası: {e}")
            return []
    
    def solve_recaptcha(self, driver):
        """reCAPTCHA'yı çözmeye çalışır."""
        max_attempts = 3
        attempts = 0
        
        while attempts < max_attempts:
            try:
                # Hedef nesneyi al
                target_object = self.extract_target_object(driver)
                if not target_object:
                    return False
                
                # Challenge görüntülerini al
                captcha_images = self.extract_captcha_images(driver)
                if not captcha_images:
                    return False
                
                # Her görüntüyü analiz et ve hedef nesneyi içerenleri seç
                matches_found = False
                for img_data in captcha_images:
                    detections = self.detect_objects(img_data["image"])
                    
                    if self.matches_target(detections, target_object):
                        print(f"Eşleşme bulundu! Görüntü {img_data['index']}")
                        
                        # Görüntüye tıkla
                        ActionChains(driver).move_to_element(img_data["element"]).click().perform()
                        time.sleep(0.5)
                        matches_found = True
                
                # Eşleşme bulunamadıysa
                if not matches_found:
                    print("Hiç eşleşme bulunamadı, yeni görev isteniyor...")
                    try:
                        # Yenile/Atla butonuna tıkla
                        reload_button = driver.find_element(By.ID, "recaptcha-reload-button")
                        reload_button.click()
                        time.sleep(2)
                        attempts += 1
                        continue
                    except:
                        pass
                
                # Doğrulama butonuna tıkla
                verify_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "recaptcha-verify-button"))
                )
                verify_button.click()
                
                # Sonucu kontrol et
                time.sleep(3)
                
                try:
                    # Başarısız olma durumunda yeni bir challenge yüklenir
                    new_challenge = driver.find_element(By.CSS_SELECTOR, ".rc-imageselect-incorrect-response")
                    if new_challenge.is_displayed():
                        print("reCAPTCHA çözülemedi, yeniden deneniyor...")
                        attempts += 1
                        continue
                except:
                    # Yeni challenge yüklenmezse başarılı olmuş olabilir
                    pass
                
                # Ana frame'e geri dön
                driver.switch_to.default_content()
                
                # Başarı kontrolü
                time.sleep(2)
                try:
                    iframe = driver.find_element(By.CSS_SELECTOR, "iframe[title='reCAPTCHA']")
                    driver.switch_to.frame(iframe)
                    
                    success = driver.find_element(By.CSS_SELECTOR, ".recaptcha-checkbox-checked")
                    if success:
                        print("reCAPTCHA başarıyla çözüldü!")
                        driver.switch_to.default_content()
                        return True
                except:
                    pass
                
                driver.switch_to.default_content()
                attempts += 1
                
            except Exception as e:
                print(f"reCAPTCHA çözme hatası: {e}")
                driver.switch_to.default_content()
                attempts += 1
        
        print(f"Maksimum deneme sayısına ulaşıldı ({max_attempts})")
        return False

# Test kullanımı
if __name__ == "__main__":
    solver = YOLORecaptchaSolver()
    
    # Tarayıcıyı başlat
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    driver = webdriver.Chrome(options=options)
    
    # reCAPTCHA içeren bir siteye git
    driver.get("https://www.google.com/recaptcha/api2/demo")
    
    try:
        # reCAPTCHA'yı çöz
        if solver.solve_recaptcha(driver):
            print("reCAPTCHA başarıyla çözüldü!")
        else:
            print("reCAPTCHA çözülemedi.")
    finally:
        # Çıkmadan önce 5 saniye bekle
        time.sleep(5)
        driver.quit()