
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: image_packing

short_description: Pack images to a bigger picture.

version_added: "1.0.0"

description: Pack images to a bigger picture using a strip packing heuristic.

options:
    image_paths:
        description: A list of image paths to be packed.
        required: true
        type: list
        elements: str
    max_width:
        description: The max width to be used.
        required: false
        type: int
    output:
        description: The output path for the packed image
        required: false
        type: str
    chdir:
        description: The current working directory
        required: false
        type: str

author:
    - José Pedro Fernandes (@jpdiasfernandes)
'''

EXAMPLES = r'''
# Pack a list of images to a bigger picture, with max width
# set to 1400
- name: Pack images to a single bigger picture
    image_packing:
        image_paths:
            - small_image.png
            - bigger_image.png
            - irregular_image.png
            - square_image.png
        max_width:  1400

# Pack a list of images to a bigger picture, with max width
# of result being the max width of the images given
- name: Pack images to a single bigger picture
    plot_energy:
        image_paths:
            - small_image.png
            - bigger_image.png
            - irregular_image.png
            - square_image.png
'''

RETURN = r'''

'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.ph import phspprg
from collections import namedtuple
from PIL import Image
import os


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        image_paths=dict(type='list', required=True, elements='str'),
        max_width=dict(type='int', required=False),
        output=dict(type='str', required=False)
    )


    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        image_paths = module.params['image_paths'],
        changed=True
    )

    if module.check_mode:
        module.exit_json(**result)

    images = load_images_from_path(module.params['image_paths'])

    if module.params['max_width'] == None:
        max_width = get_max_width(images)
    else:
        max_width = module.params['max_width']

    if module.params['output'] == None:
        output = "packed_image.png"
    else:
        output = module.params['output']

    if module.params['chdir'] != None:
        os.chdir(module.params['chdir'])


    width, height = merge_images(images, max_width, output)

    result["width"] = width
    result["height"] = height

    module.exit_json(**result)


ImageObj = namedtuple('ImageObj', ['image', 'width', 'height'])

def get_max_width(images):
    return (max(images, key=lambda img: img.width)).width

def create_image(images, metadata, width, height, output):
    new_image = Image.new('RGB', size=(width, height))
    for idx, image in enumerate(images):
        x,y,w,h = metadata[idx]
        raw_image = image.image
        if w != image.width:
            raw_image = image.image.rotate(90, expand=True)
        new_image.paste(raw_image, (x,height-(y+h)))

    new_image.save(output)

def load_images_from_path(paths):
    images = []
    for path in paths:
        img = Image.open(path)
        images.append(ImageObj(img, img.width, img.height))
    return images


def merge_images(images, max_width, output):
    boxes = []
    for image in images:
        boxes.append([image.width, image.height])

    for idx, box in enumerate(boxes):
        print(f"{idx} : (w {box[0]}, h {box[1]})")

    width = max_width
    height, rectangles = phspprg(width, boxes)

    create_image(images, rectangles, width, height, output)

    return width, height

if __name__ == "__main__":
    run_module()
