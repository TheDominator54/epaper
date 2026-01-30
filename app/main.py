import time

# Example for a 2.13" driver; change to match your model.
# Drivers live in lib/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd/
from waveshare_epd import epd2in13_V4  # <-- you may need epd2in13, epd2in13b, epd7in5_V2, etc.
from PIL import Image, ImageDraw, ImageFont

def main():
    epd = epd2in13_V4.EPD()
    epd.init()
    epd.Clear(0xFF)

    image = Image.new('1', (epd.height, epd.width), 255)  # 1-bit
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), "Hello Dom 👋", font=ImageFont.load_default(), fill=0)

    epd.display(epd.getbuffer(image))
    time.sleep(2)

    # optional sleep (keeps image without full power)
    epd.sleep()

if __name__ == "__main__":
    main()
