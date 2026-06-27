import xml.etree.ElementTree as ET

def clean_kml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    return tree
