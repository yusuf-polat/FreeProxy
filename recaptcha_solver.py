from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import requests
import speech_recognition as sr
import os
from pydub import AudioSegment

def solve_recaptcha_v2():
    # Set up Chrome options
    chrome_options = Options()
    # Uncomment the line below if you want to run in headless mode
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Set up the Chrome driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Navigate to the reCAPTCHA demo page
        print("Navigating to the reCAPTCHA demo page...")
        driver.get("https://testrecaptcha.github.io/")
        
        # Wait for the reCAPTCHA iframe to load
        print("Waiting for reCAPTCHA to load...")
        WebDriverWait(driver, 10).until(
            EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe[title='reCAPTCHA']"))
        )
        
        # Click on the reCAPTCHA checkbox
        print("Clicking on the reCAPTCHA checkbox...")
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.recaptcha-checkbox-border"))
        ).click()
        
        # Switch back to the main content
        driver.switch_to.default_content()
        
        # Wait for the audio challenge iframe to appear and switch to it
        print("Waiting for audio challenge...")
        WebDriverWait(driver, 10).until(
            EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe[title='recaptcha challenge expires in two minutes']"))
        )
        
        # Click on the audio challenge button
        print("Clicking on the audio challenge button...")
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "recaptcha-audio-button"))
        ).click()
        
        # Wait for the audio to be available
        print("Waiting for audio to be available...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "audio-source"))
        )
        
        # Get the audio URL
        audio_url = driver.find_element(By.ID, "audio-source").get_attribute("src")
        print(f"Audio URL: {audio_url}")
        
        # ---- MANUEL SES İŞLEME KISMI ----
        # Ses dosyasını indir
        print("Downloading audio file...")
        mp3_file = "captcha_audio.mp3"
        wav_file = "captcha_audio.wav"
        response = requests.get(audio_url)
        with open(mp3_file, "wb") as f:
            f.write(response.content)
        
        # MP3'ten WAV'a dönüştür
        print("Converting MP3 to WAV...")
        sound = AudioSegment.from_mp3(mp3_file)
        sound.export(wav_file, format="wav")
        
        # Ses dosyasını metne çevir
        print("Converting audio to text...")
        r = sr.Recognizer()
        with sr.AudioFile(wav_file) as source:
            audio_data = r.record(source)
            try:
                audio_response = r.recognize_google(audio_data)
                print(f"Transcribed text: {audio_response}")
            except sr.UnknownValueError:
                print("Google Speech Recognition could not understand audio")
                audio_response = ""
            except sr.RequestError as e:
                print(f"Could not request results from Google Speech Recognition service; {e}")
                audio_response = ""
        
        # Geçici dosyaları temizle
        os.remove(mp3_file)
        os.remove(wav_file)
        
        # Cevap boş değilse devam et
        if audio_response:
            # Enter the response in the text field
            print("Entering the response...")
            driver.find_element(By.ID, "audio-response").send_keys(audio_response)
            
            # Click the verify button
            print("Clicking verify button...")
            driver.find_element(By.ID, "recaptcha-verify-button").click()
            
            # Switch back to the main content
            driver.switch_to.default_content()
            
            # Wait for the reCAPTCHA to be solved
            print("Waiting for reCAPTCHA to be solved...")
            time.sleep(3)
            
            # Check if the form is now submittable
            print("Checking if form is submittable...")
            submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            if submit_button.is_enabled():
                print("reCAPTCHA solved successfully!")
                submit_button.click()
                print("Form submitted!")
            else:
                print("reCAPTCHA not solved correctly.")
        else:
            print("Failed to transcribe audio. Cannot proceed.")
        
        # Wait to see the result
        time.sleep(5)
        
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Close the browser
        print("Closing browser...")
        driver.quit()

if __name__ == "__main__":
    solve_recaptcha_v2()
    print("Script completed.")