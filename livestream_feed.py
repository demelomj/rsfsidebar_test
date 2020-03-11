# System imports
import os
import sys
from time import time
from io import BytesIO
import requests
# Third-party imports
from PIL import Image
# Project imports
import config
from livestream_sources import twitch
import log


def build():
    log.log('Beginning to build the livestream feed...')
    livestreamFeedStartTime = time()

    settings = config.readJson('settings.json')

    # Fetch all the livestream data
    livestreams = []
    services = (s.lower() for s in settings['sidebar']['livestreams']['services'])
    if settings['sidebar']['livestreams']['services'] != []:
        if 'twitch' in services:
            livestreams += twitch.Twitch().get()
    else:
        livestreams = twitch.Twitch().get()

    # Return a blank container's markdown if there are no streams
    if len(livestreams) == 0 and settings['sidebar']['livestreams']['none_message'] != '':
        return {
            'markdown': '**BETA Live Stream List** |  \n ------------- | --------------------- | \n %s' \
                        % settings['sidebar']['livestreams']['none_message'],
            'spritesheet_path': None
        }

    # Sort the livestreams by number of viewers, descending
    livestreams = sorted(livestreams, key=lambda channel: channel['viewers_raw'], reverse=True)
    # Trim off the remainder if there were more than the number we're supposed to use
    if len(livestreams) > settings['sidebar']['livestreams']['max_shown']:
        livestreams = livestreams[:settings['sidebar']['livestreams']['max_shown']]

    # TODO: Clean up all this code, the naming is all horrid

    templates = config.readJson('templates.json')

    # Goes in between items in the livestream list
    if 'livestreams' in templates and 'separator' in templates['livestreams']:
        separator = templates['livestreams']['separator']
    else:
        separator = '>>[](#separator)'
    separator = '' + separator + '\n'

    # Template for a stream in the livestream list
    if 'livestreams' in templates and 'stream' in templates['livestreams']:
        livestreamMdTemplate = templates['livestreams']['stream']
        bannerstreamMdTemplate = ('[__TITLE__ __VIEWERS__ @ __STREAMER__](__URL__)')
    else:
        # Default template
        livestreamMdTemplate = ('[__TITLE__](__URL__) __VIEWERS__ @ __STREAMER__')
        bannerstreamMdTemplate = ('[__TITLE__ __VIEWERS__ @ __STREAMER__](__URL__)')
    livestreamMdTemplate += separator

    # Template for the livestreams section heading
    if 'livestreams' in 'templates' and 'heading' in templates['livestreams']:
        livestreamsMd = templates['livestreams']['heading'] + '\n\n'
    else:
        # Default heading
        livestreamsMd = '**BETA Live Stream List** | \n ------------- | --------------------- | \n'

    i = 0
    bannerstream = ""
    for livestream in livestreams:
        livestreamMd = livestreamMdTemplate
        livestreamMd = (livestreamMd
                        .replace('__TITLE__', livestream['title'])
                        .replace('__URL__', livestream['url'])
                        .replace('__INDEX__', str(i))
                        .replace('__VIEWERS__', livestream['viewers'])
                        .replace('__STREAMER__', livestream['streamer']))
        livestreamsMd += livestreamMd
        i += 1
        if i == 1:
            bannerstream = bannerstreamMdTemplate
            bannerstream = (bannerstream
                        .replace('__TITLE__', livestream['title'])
                        .replace('__URL__', livestream['url'])
                        .replace('__INDEX__', str(i))
                        .replace('__VIEWERS__', livestream['viewers'])
                        .replace('__STREAMER__', livestream['streamer']))

    if 'see_all_link' in settings['sidebar']['livestreams']:
        if 'livestreams' in templates and 'see_all' in templates['livestreams']:
            see_all_template = templates['livestreams']['see_all']
        else:
            see_all_template = '**[See all](__LINK__)**'
        see_all_template = see_all_template.replace('__LINK__', settings['sidebar']['livestreams']['see_all_link'])
        livestreamsMd += see_all_template

    # This %%IGNORE%% bit is necessary because any lines starting with a hashtag
    # are headers in Reddit Markdown, but comments in YAML. These lines must be
    # preceded with something unique so that we can parse them properly.
        livestreamsMd = livestreamsMd.replace('%%IGNORE%%', '')

    spritesheetPath = None

    if settings['sidebar']['livestreams']['show_thumbnails']:
        uploadThumbnailsStartTime = time()
        log.log('\tGenerating spritesheet...')
        spritesheetPath = generateSpritesheet([x['thumbnail'] for x in livestreams])
        log.log('\t\t ... done! ' + '\BLUE(%s s)' % str(round(time() - uploadThumbnailsStartTime, 3)))

    characters = '\YELLOW(%d characters)' % len(livestreamsMd)
    elapsedTime = '\BLUE(%s s)' % str(round(time() - livestreamFeedStartTime, 3))
    log.log('Done building livestream feed. %s %s' % (characters, elapsedTime))

    return {
        'markdown': livestreamsMd,
        'spritesheet_path': spritesheetPath,
        'banner': bannerstream
    }


# Our sprites by default are 45 x 30
# This function returns a path to the generated spritesheet
def generateSpritesheet(imageURLs, width=45, height=30):
    if len(imageURLs) == 0:
        return None
    images = []
    # Fetch the images and convert them to PIL objects
    for url in imageURLs:
        try:
            rawImage = requests.get(url).content
        except requests.exceptions.RequestException as e:
            try:
                rawImage = requests.get(url.replace('.jpg', '.png')).content
            except:
                log.error('Problem grabbing image: %s\nError Message: %s' % (url, str(e)), 1)
                return False
        images.append(Image.open(BytesIO(rawImage)))

    # Resize all images to match our standard thumbnail size
    for image in images:
        size = image.size
        if size[0] != width or size[1] != height:
            image = image.thumbnail((width, height), Image.ANTIALIAS)

    # Create the canvas on which to paint our sprites
    spritesheet = Image.new(
        mode='RGB',
        size=(width * len(images), height),
        color=(0, 0, 0, 1)
    )

    # Paint them sprites, baby
    for i, image in enumerate(images):
        location = width * i
        spritesheet.paste(image, (location, int((height - image.size[1]) / 2)))

    # Save the spritesheet to the following path and return the path.
    # The os.path.blahblah code is to ensure it goes in the right directory
    savePath = os.path.dirname(os.path.abspath(sys.argv[0])) + '/app-cache/spritesheet.jpg'
    spritesheet.save(savePath, transparency=0)

    return savePath
