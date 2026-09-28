from selenium import webdriver
import time

driver = webdriver.Chrome()

driver.get("https://infinite-scroll.com/demo/full-page/?utm_source=chatgpt.com")

time.sleep(10)

print(driver.title)

driver.quit()