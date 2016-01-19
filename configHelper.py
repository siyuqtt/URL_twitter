__author__ = 'siyuqiu'
import xml.etree.ElementTree as ET
tree = ET.parse('config')
root = tree.getroot()

class config:
    def __init__(self):
        self.accesstoken = root.find('ACCESS_TOKEN').text
        self.accessscecret = root.find('ACCESS_SECRET').text
        self.consumertoken = root.find('CONSUMER_KEY').text
        self.consumersecret = root.find('CONSUMER_SECRET').text
myconfig = config()