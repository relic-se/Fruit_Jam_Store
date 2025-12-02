# SPDX-FileCopyrightText: 2025 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

# load included modules if we aren't installed on the root path
if len(__file__.split("/")[:-1]) > 1:
    lib_path = "/".join(__file__.split("/")[:-1]) + "/lib"
    try:
        import os
        os.stat(lib_path)
    except:
        pass
    else:
        import sys
        sys.path.append(lib_path)

import displayio
import gc
import math
import os
import sys
import supervisor
from terminalio import FONT
import time
import json

from adafruit_anchored_group import AnchoredGroup
from adafruit_anchored_tilegrid import AnchoredTileGrid
from adafruit_button import Button
from adafruit_display_text.label import Label
from adafruit_display_text.text_box import TextBox
from adafruit_displayio_layout.layouts.grid_layout import GridLayout
import adafruit_fruitjam
import adafruit_fruitjam.network
import adafruit_fruitjam.peripherals
import adafruit_imageload
from adafruit_portalbase.network import HttpError
import adafruit_usb_host_mouse
import asyncio

from zipfile import ZipFile

try:
    import typing
except ImportError:
    pass

# program constants
APPLICATIONS_URL = "https://raw.githubusercontent.com/relic-se/Fruit_Jam_Store/refs/heads/main/database/applications.json"
METADATA_URL = "https://raw.githubusercontent.com/{:s}/refs/heads/main/metadata.json"
REPO_URL = "https://api.github.com/repos/{:s}"
ICON_URL = "https://raw.githubusercontent.com/{:s}/{:s}/{:s}"
RELEASE_URL = "https://api.github.com/repos/{:s}/releases/latest"

# file operations

def exists(path: str) -> bool:
    try:
        os.stat(path)
    except:
        return False
    else:
        return True
    
def mkdir(path: str, isfile: bool = False) -> bool:
    parts = path.strip("/").split("/")
    if isfile:
        parts = parts[:-1]
    for i in range(len(parts)):
        dirpath = "/" + "/".join(parts[:i+1])
        if not exists(dirpath):
            os.mkdir(dirpath)

def rmtree(dirpath: str) -> None:
    for name in os.listdir(dirpath):
        filepath = dirpath + "/" + name
        st_mode = os.stat(filepath)[0]
        if st_mode & 0x8000:
            os.remove(filepath)
        elif st_mode & 0x4000:
            rmtree(filepath)
    os.rmdir(dirpath)

def extractall(zf: ZipFile, destination: str, source: str = "") -> None:
    for srcpath in zf:
        if srcpath.startswith(source + "/"):
            destpath = destination + "/" + srcpath[len(source) + 1:]
            mkdir(destpath, True)
            with open(destpath, "wb") as f:
                f.write(zf.read(zf[srcpath]))

def is_app_installed(name: str) -> bool:
    return exists("/sd/apps/{:s}".format(name))

# file download + caching

def _download_file(url: str, extension: str, name: str|None = None) -> str:
    if not extension.startswith("."):
        extension = "." + extension

    if name is None:
        name = url.split("/")[-1][:-len(extension)]
    elif name.endswith(extension):
        name = name[:-len(extension)]
    path = "/sd/.cache/{:s}{:s}".format(name, extension)

    # download file if it doesn't already exist
    if not exists(path):
        fj.network.wget(url, path)
    # TODO: Cache duration
    return path

def download_image(url: str, name: str|None = None) -> str:
    return _download_file(
        url=url,
        extension=".bmp",
        name=name,
    )

def download_json(url: str, name: str|None = None) -> str:
    path = _download_file(
        url=url,
        extension=".json",
        name=name,
    )
    with open(path, "r") as f:
        data = json.loads(f.read())
    return data

def download_zip(url: str, name: str|None = None) -> str:
    return _download_file(
        url=url,
        extension=".zip",
        name=name,
    )

# get Fruit Jam OS config if available
try:
    import launcher_config
    config = launcher_config.LauncherConfig()
except ImportError:
    config = None

bg_palette = displayio.Palette(1)
bg_palette[0] = config.palette_bg if config is not None else 0x222222

fg_palette = displayio.Palette(1)
fg_palette[0] = config.palette_fg if config is not None else 0xffffff

# setup display
displayio.release_displays()
try:
    adafruit_fruitjam.peripherals.request_display_config()  # user display configuration
except ValueError:  # invalid user config or no user config provided
    adafruit_fruitjam.peripherals.request_display_config(720, 400)  # default display size
display = supervisor.runtime.display

# setup FruitJam peripherals and networking
fj = adafruit_fruitjam.FruitJam()

# load images
default_icon_bmp, default_icon_palette = adafruit_imageload.load("bitmaps/default_icon.bmp")
default_icon_palette.make_transparent(0)

installed_bmp, installed_palette = adafruit_imageload.load("bitmaps/installed.bmp")
installed_palette.make_transparent(1)
installed_palette[0] = config.palette_bg if config is not None else 0x222222
installed_palette[2] = config.palette_fg if config is not None else 0xffffff

left_bmp, left_palette = adafruit_imageload.load("bitmaps/arrow_left.bmp")
left_palette.make_transparent(0)
right_bmp, right_palette = adafruit_imageload.load("bitmaps/arrow_right.bmp")
right_palette.make_transparent(0)
left_palette[2] = right_palette[2] = (config.palette_arrow if config is not None else 0x004abe)

exit_bmp, exit_palette = adafruit_imageload.load("bitmaps/exit.bmp")
exit_palette.make_transparent(0)
exit_palette[1] = config.palette_fg if config is not None else 0xffffff

# display constants
SCALE = 2 if display.width > 360 else 1

DISPLAY_WIDTH = display.width // SCALE
DISPLAY_HEIGHT = display.height // SCALE

TITLE_HEIGHT = 16

STATUS_HEIGHT = 16
STATUS_PADDING = 4

MENU_HEIGHT = 24
MENU_GAP = 8

PAGE_COLUMNS = SCALE
PAGE_ROWS = 3
PAGE_SIZE = PAGE_COLUMNS * PAGE_ROWS

ARROW_MARGIN = 2

GRID_MARGIN = 8 * SCALE
GRID_WIDTH = display.width - GRID_MARGIN * 2 - (ARROW_MARGIN + left_bmp.width) * SCALE * 2
GRID_HEIGHT = display.height - TITLE_HEIGHT * SCALE - MENU_HEIGHT * SCALE - GRID_MARGIN * 2 - STATUS_HEIGHT

ITEM_WIDTH = GRID_WIDTH // PAGE_COLUMNS
ITEM_HEIGHT = GRID_HEIGHT // PAGE_ROWS

DIALOG_MARGIN = 16 * SCALE
DIALOG_BORDER = SCALE
DIALOG_WIDTH = display.width - DIALOG_MARGIN * 2 - (ARROW_MARGIN + left_bmp.width) * SCALE * 2
DIALOG_HEIGHT = display.height - TITLE_HEIGHT * SCALE - DIALOG_MARGIN * 2 - STATUS_HEIGHT
DIALOG_BUTTON_WIDTH = DIALOG_WIDTH // SCALE // 4

BUTTON_PROPS = {
    "height": MENU_HEIGHT,
    "label_font": FONT,
    "style": Button.ROUNDRECT,
    "fill_color": (config.palette_bg if config is not None else 0x222222),
    "label_color": (config.palette_fg if config is not None else 0xffffff),
    "outline_color": (config.palette_fg if config is not None else 0xffffff),
    "selected_fill": (config.palette_fg if config is not None else 0xffffff),
    "selected_label": (config.palette_bg if config is not None else 0x222222),
}

# create groups
root_group = displayio.Group()
display.root_group = root_group

bg_tg = displayio.TileGrid(
    bitmap=displayio.Bitmap(display.width, display.height, 1),
    pixel_shader=bg_palette,
)
root_group.append(bg_tg)

# add title
title_group = displayio.Group(scale=SCALE)
root_group.append(title_group)

title_label = Label(
    font=FONT,
    text="Fruit Jam Store",
    color=(config.palette_fg if config is not None else 0xffffff),
    anchor_point=(0.5, 0.5),
    anchored_position=(DISPLAY_WIDTH // 2, TITLE_HEIGHT // 2),
)
title_group.append(title_label)

# add status bar
status_group = displayio.Group()
root_group.append(status_group)

status_bg_tg = displayio.TileGrid(
    bitmap=displayio.Bitmap(display.width, STATUS_HEIGHT, 1),
    pixel_shader=fg_palette,
    y=display.height - STATUS_HEIGHT,
)
status_group.append(status_bg_tg)

status_label = Label(
    font=FONT,
    text="Loading...",
    color=(config.palette_bg if config is not None else 0x222222),
    anchor_point=(0, 0.5),
    anchored_position=(STATUS_PADDING, display.height - STATUS_HEIGHT // 2)
)
status_group.append(status_label)

page_label = Label(
    font=FONT,
    text="0/0",
    color=(config.palette_bg if config is not None else 0x222222),
    anchor_point=(1, 0.5),
    anchored_position=(display.width - STATUS_PADDING, display.height - STATUS_HEIGHT // 2)
)
status_group.append(page_label)

def log(msg: str) -> None:
    status_label.text = msg
    print(msg)

# check that sd card is mounted
def reset(timeout:int = 0) -> None:
    if timeout > 0:
        time.sleep(timeout)
    fj.peripherals.deinit()
    supervisor.reload()

if not fj.sd_check():
    log("SD card not mounted! SD card installation required for this application.")
    reset(3)

# create necessary directories on sd card if they don't already exist
for dirname in ("apps", ".cache"):
    mkdir("/sd/" + dirname)

# download applications database
try:
    applications = json.loads(fj.fetch(
        APPLICATIONS_URL,
        force_content_type=adafruit_fruitjam.network.CONTENT_JSON,
        timeout=10,
    ))
    if type(applications) is int:
        raise ValueError("{:d} response".format(applications))
except (OSError, ValueError, AttributeError) as e:
    log("Unable to fetch applications database! {:s}".format(str(e)))
    reset(3)

categories = list(applications.keys())
selected_category = None

# setup menu
category_group = displayio.Group(scale=SCALE)
root_group.append(category_group)
MENU_WIDTH = (DISPLAY_WIDTH - MENU_GAP * (len(categories) + 1)) // len(categories)
for index, category in enumerate(categories):
    category_button = Button(
        x=(MENU_WIDTH + MENU_GAP) * index + MENU_GAP,
        y=TITLE_HEIGHT,
        width=MENU_WIDTH,
        label=category,
        **BUTTON_PROPS,
    )
    category_group.append(category_button)

# setup items
item_grid = GridLayout(
    x=(display.width - GRID_WIDTH) // 2,
    y=TITLE_HEIGHT * SCALE + MENU_HEIGHT * SCALE + GRID_MARGIN,
    width=GRID_WIDTH,
    height=GRID_HEIGHT,
    grid_size=(PAGE_COLUMNS, PAGE_ROWS),
    divider_lines=False,
)
root_group.append(item_grid)

for index in range(PAGE_SIZE):
    item_group = AnchoredGroup()
    item_group.hidden = True

    item_icon = displayio.TileGrid(
        bitmap=default_icon_bmp,
        pixel_shader=default_icon_palette,
        x=(ITEM_HEIGHT - default_icon_bmp.height) // 2,
        y=(ITEM_HEIGHT - default_icon_bmp.height) // 2,
    )
    item_group.append(item_icon)

    item_installed = displayio.TileGrid(
        bitmap=installed_bmp,
        pixel_shader=installed_palette,
        x=item_icon.x + 2, y=item_icon.y + 2,
    )
    item_group.append(item_installed)

    item_title = Label(
        font=FONT,
        text="[title]",
        color=(config.palette_fg if config is not None else 0xffffff),
        anchor_point=(0, 0),
        anchored_position=(ITEM_HEIGHT, (ITEM_HEIGHT - item_icon.tile_height) // 2),
        scale=SCALE,
    )
    item_group.append(item_title)

    item_author = Label(
        font=FONT,
        text="[author]",
        color=(config.palette_fg if config is not None else 0xffffff),
        anchor_point=(0, 0),
        anchored_position=(ITEM_HEIGHT, item_title.y + item_title.height),
    )
    item_group.append(item_author)

    item_description = TextBox(
        font=FONT,
        text="[description]",
        width=ITEM_WIDTH - ITEM_HEIGHT,
        height=item_icon.tile_height - item_title.height - item_author.height,
        align=TextBox.ALIGN_LEFT,
        color=(config.palette_fg if config is not None else 0xffffff),
        anchor_point=(0, 0),
        anchored_position=(ITEM_HEIGHT, item_author.y + item_author.height),
    )
    item_group.append(item_description)

    item_grid.add_content(
        cell_content=item_group,
        grid_position=(index % PAGE_COLUMNS, index // PAGE_COLUMNS),
        cell_size=(1, 1),
    )

# setup arrows
original_arrow_btn_color = left_palette[2]

arrow_group = displayio.Group(scale=SCALE)
root_group.append(arrow_group)

left_arrow = AnchoredTileGrid(
    bitmap=left_bmp,
    pixel_shader=left_palette,
)
left_arrow.anchor_point = (0, 0.5)
left_arrow.anchored_position = (0, (DISPLAY_HEIGHT // 2) - 2)
arrow_group.append(left_arrow)

right_arrow = AnchoredTileGrid(
    bitmap=right_bmp,
    pixel_shader=right_palette,
)
right_arrow.anchor_point = (1.0, 0.5)
right_arrow.anchored_position = (DISPLAY_WIDTH, (DISPLAY_HEIGHT // 2) - 2)
arrow_group.append(right_arrow)

# setup exit icon
exit_tg = AnchoredTileGrid(
    bitmap=exit_bmp,
    pixel_shader=exit_palette,
)
exit_tg.anchor_point = (0.5, 0.5)
exit_tg.anchored_position = (TITLE_HEIGHT // 2, TITLE_HEIGHT // 2)
arrow_group.append(exit_tg)

# setup dialog
dialog_group = displayio.Group()
dialog_group.hidden = True
root_group.append(dialog_group)

dialog_border = displayio.TileGrid(
    bitmap=displayio.Bitmap(DIALOG_WIDTH, DIALOG_HEIGHT, 1),
    pixel_shader=fg_palette,
    x=(display.width - DIALOG_WIDTH) // 2,
    y=TITLE_HEIGHT * SCALE + DIALOG_MARGIN,
)
dialog_group.append(dialog_border)

dialog_bg = displayio.TileGrid(
    bitmap=displayio.Bitmap(DIALOG_WIDTH - DIALOG_BORDER * 2, DIALOG_HEIGHT - DIALOG_BORDER * 2, 1),
    pixel_shader=bg_palette,
    x=dialog_border.x + DIALOG_BORDER,
    y=dialog_border.y + DIALOG_BORDER,
)
dialog_group.append(dialog_bg)

dialog_content = TextBox(
    font=FONT,
    text="[content]",
    width=DIALOG_WIDTH - DIALOG_BORDER * 2 - DIALOG_MARGIN * 2,
    height=DIALOG_HEIGHT - DIALOG_BORDER * 2 - DIALOG_MARGIN * 3 - MENU_HEIGHT,
    align=TextBox.ALIGN_CENTER,
    color=(config.palette_fg if config is not None else 0xffffff),
    x=dialog_bg.x + DIALOG_MARGIN,
    y=dialog_bg.y + DIALOG_MARGIN,
)
dialog_group.append(dialog_content)

dialog_buttons = displayio.Group(scale=SCALE)
dialog_buttons.hidden = True
root_group.append(dialog_buttons)

class DialogButton(Button):
    def __init__(self, action: typing.Callable = None, **kwargs):
        self._action = action
        super().__init__(**kwargs)
    def click(self) -> None:
        if self._action is not None:
            self.selected = True
            self._action()

def show_dialog(content: str, actions: list = None) -> None:
    # update content
    dialog_content.text = content

    # create buttons
    if actions is not None:
        button_width = min(
            DIALOG_BUTTON_WIDTH,
            (DIALOG_WIDTH - (DIALOG_BORDER // SCALE + DIALOG_MARGIN // SCALE) * 2 - MENU_GAP * (len(actions) - 1)) // len(actions)
        )
        buttons_width = (button_width + MENU_GAP) * len(actions) - MENU_GAP
        for index, (label, action) in enumerate(actions):
            dialog_buttons.append(DialogButton(
                action=action,
                label=label,
                x=(DISPLAY_WIDTH - buttons_width) // 2 + (button_width + MENU_GAP) * index,
                y=DISPLAY_HEIGHT - (STATUS_HEIGHT + DIALOG_MARGIN * 2 + DIALOG_BORDER) // SCALE - MENU_HEIGHT,
                width=button_width,
                **BUTTON_PROPS,
            ))

    # hide other UI elements
    category_group.hidden = True
    item_grid.hidden = True
    arrow_group.hidden = True

    # show dialog
    dialog_group.hidden = False
    dialog_buttons.hidden = False

def hide_dialog() -> None:
    # clear text
    dialog_content.text = ""

    # remove buttons
    while len(dialog_buttons):
        dialog_buttons.pop()

    # hide dialog
    dialog_group.hidden = True
    dialog_buttons.hidden = True

    # show other UI elements
    category_group.hidden = False
    item_grid.hidden = False
    arrow_group.hidden = False

# item navigation

def select_category(name: str) -> None:
    global selected_category
    if name not in categories or name == selected_category:
        return
    selected_category = name

    # update button states
    for category_button in category_group:
        category_button.selected = category_button.label == name
    
    # hide all items
    for index in range(PAGE_SIZE):
        item_grid.get_content((index % PAGE_COLUMNS, index // PAGE_COLUMNS)).hidden = True

    # load first page of items
    show_page()

current_page = 0
def show_page(page: int = 0) -> None:
    global selected_category, current_page

    # determine indices
    start = page * PAGE_SIZE
    end = min((page + 1) * PAGE_SIZE, len(applications[selected_category]))
    if start < 0 or start >= len(applications[selected_category]):
        return

    # hide all items
    for index in range(PAGE_SIZE):
        item_grid.get_content((index % PAGE_COLUMNS, index // PAGE_COLUMNS)).hidden = True

    # update page label
    current_page = page
    total_pages = math.ceil(len(applications[selected_category]) / PAGE_SIZE)
    page_label.text = "{:d}/{:d}".format(page + 1, total_pages)

    # toggle arrows
    left_arrow.hidden = not page
    right_arrow.hidden = page + 1 == total_pages

    # display default details
    for index in range(start, end):
        item_group = item_grid.get_content((index % PAGE_COLUMNS, index // PAGE_COLUMNS))
        item_icon, item_installed, item_title, item_author, item_description = item_group

        full_name = applications[selected_category][index]
        repo_owner, repo_name = full_name.split("/")

        # format title from repository name
        title = repo_name.replace("-", " ").replace("_", " ").strip()
        title = " ".join(map(lambda word: word[0].upper() + word[1:].lower(), title.split(" ")))
        if title.startswith("Fruit Jam"):
            title = title[len("Fruit Jam"):].strip()
        
        # set default details
        item_icon.bitmap = default_icon_bmp
        item_icon.pixel_shader = default_icon_palette
        item_installed.hidden = not is_app_installed(repo_name)
        item_title.text = title
        item_author.text = repo_owner
        item_description.text = "Loading..."
        item_group.hidden = False
    
    # read external application data
    for index in range(start, end):
        item_group = item_grid.get_content((index % PAGE_COLUMNS, index // PAGE_COLUMNS))
        item_icon, item_installed, item_title, item_author, item_description = item_group

        full_name = applications[selected_category][index]

        log("Reading repository data from {:s}".format(full_name))

        # get repository info
        try:
            repository = download_json(
                url=REPO_URL.format(full_name),
                name=full_name.replace("/", "_"),
            )
        except (OSError, ValueError, HttpError) as e:
            item_description.text = ""
            log("Unable to read repository data from {:s}! {:s}".format(full_name, str(e)))
            time.sleep(1)
            continue
        else:
            item_author.text = repository["owner"]["login"]
            item_description.text = repository["description"]

        # read metadata from repository
        log("Reading metadata from {:s}".format(full_name))
        try:
            metadata = download_json(
                url=METADATA_URL.format(full_name),
                name=full_name.replace("/", "_") + "_metadata",
            )
        except (OSError, ValueError, HttpError) as e:
            log("Unable to read metadata from {:s}! {:s}".format(full_name, str(e)))
        else:
            item_title.text = metadata["title"]

            if "description" in metadata:
                item_description.text = metadata["description"]

            if "icon" in metadata:
                log("Downloading icon from {:s}".format(full_name))
                try:
                    icon_path = download_image(
                        ICON_URL.format(full_name, repository["default_branch"], metadata["icon"]),
                        repository["name"] + "_" + metadata["icon"],
                    )
                except (OSError, ValueError, HttpError) as e:
                    log("Unable to download icon image from {:s}! {:s}".format(full_name, str(e)))
                else:
                    icon_bmp, icon_palette = adafruit_imageload.load(icon_path)
                    item_icon.bitmap = icon_bmp
                    item_icon.pixel_shader = icon_palette

        # cleanup before loading next item
        gc.collect()

    log("Page loaded!")

def next_page() -> None:
    global current_page
    show_page(current_page + 1)

def previous_page() -> None:
    global current_page
    show_page(current_page - 1)

def refresh_page() -> None:
    global current_page
    show_page(current_page)

# select first category and show page items
select_category(categories[0])

# application download

def download_application(full_name: str = None) -> bool:
    global selected_application
    if full_name is None:
        if selected_application is None:
            return False
        full_name = selected_application
    repo_owner, repo_name = full_name.split("/")
    path = "/sd/apps/{:s}".format(repo_name)
    
    if is_app_installed(repo_name):
        return False

    # get repository info
    log("Reading release data from {:s}".format(full_name))
    try:
        release = download_json(
            url=RELEASE_URL.format(full_name),
            name=full_name.replace("/", "_") + "_release",
        )
    except (OSError, ValueError, HttpError) as e:
        log("Unable to read release data from {:s}! {:s}".format(full_name, str(e)))
        return False
    
    # download project bundle
    log("Downloading release assets...")
    asset = list(filter(lambda x: x["name"].endswith(".zip"), release["assets"]))[0]
    try:
        zip_path = download_zip(asset["browser_download_url"], repo_name)
    except (OSError, ValueError, HttpError) as e:
        log("Failed to download release assets for {:s}! {:s}".format(full_name, str(e)))
        return False
    
    # read archived file
    log("Installing application...")
    result = False
    with open(zip_path, "rb") as f:
        zf = ZipFile(f)
        
        # determine correct inner path based on CP version
        major_version = int(os.uname().release.split(".")[0])
        version_name = "CircuitPython {:d}.x".format(major_version)
        for dirpath in (repo_name + "/" + version_name, version_name, repo_name, ""):
            try:
                zf[(dirpath + "/code.py").strip("/")]
            except KeyError:
                pass
            else:
                break
        
        # make sure we found code.py
        try:
            zf[(dirpath + "/code.py").strip("/")]
        except KeyError:
            log("Could not locate application files within release!")
        else:
            # extract files
            extractall(zf, path, dirpath)
            log("Successfully installed {:s}!".format(full_name))
            result = True
    
    # remove zip file
    os.remove(zip_path)
    return result

def remove_application(full_name: str = None) -> bool:
    global selected_application
    if full_name is None:
        if selected_application is None:
            return False
        full_name = selected_application
    repo_owner, repo_name = full_name.split("/")
    path = "/sd/apps/{:s}".format(repo_name)
    
    if not is_app_installed(repo_name):
        return False

    log("Deleting {:s}...".format(path))
    try:
        rmtree(path)
    except OSError as e:
        log("Failed to delete {:s}: {:s}".format(path, str(e)))
        return False
    else:
        log("Successfully deleted application!")
        return True

def open_application(full_name: str = None) -> None:
    global selected_application, current_page
    if full_name is None:
        if selected_application is None:
            return False
        full_name = selected_application
    repo_owner, repo_name = selected_application.split("/")
    launch_file = "/sd/apps/{:s}/code.py".format(repo_name)

    if is_app_installed(repo_name) and exists(launch_file):
        log("Opening {:s}...".format(repo_name))
        supervisor.set_next_code_file(
            launch_file,
            sticky_on_reload=False,
            reload_on_error=True,
            working_directory="/".join(launch_file.split("/")[:-1])
        )
        supervisor.reload()

selected_application = None
def select_application(index: int) -> None:
    global selected_category, current_page, selected_application

    index += current_page * PAGE_SIZE
    if index < 0 or index >= len(applications[selected_category]):
        return
    
    selected_application = applications[selected_category][index]
    repo_owner, repo_name = selected_application.split("/")
    
    # hide other UI elements
    category_group.hidden = True
    item_grid.hidden = True
    arrow_group.hidden = True
    
    # populate dialog info
    page_index = index % PAGE_SIZE
    item_group = item_grid.get_content((page_index % PAGE_COLUMNS, page_index // PAGE_COLUMNS))
    item_icon, item_installed, item_title, item_author, item_description = item_group

    if item_installed.hidden:
        show_dialog(
            content="Would you like to download and install \"{:s}\" by {:s} to your SD card at /sd/apps/{:s}?".format(
                item_title.text,
                item_author.text,
                repo_name
            ),
            actions=[
                ("Cancel", deselect_application),
                ("Download", toggle_application),
            ],
        )
    else:
        show_dialog(
            content="The application, \"{:s}\", is already installed. Would you like to remove it from your SD card at /sd/apps/{:s}? Any save data within /saves will be retained.".format(
                item_title.text,
                repo_name
            ),
            actions=[
                ("Cancel", deselect_application),
                ("Remove", toggle_application),
                ("Open", open_application),
            ],
        )

    dialog_group.hidden = False
    dialog_buttons.hidden = False

def deselect_application() -> None:
    global selected_application

    # invalidate selection
    selected_application = None

    # hide dialog and show other UI elements
    hide_dialog()

def toggle_application(full_name: str = None) -> bool:
    global selected_application, current_page
    if full_name is None:
        if selected_application is None:
            return False
        full_name = selected_application
    repo_owner, repo_name = selected_application.split("/")

    if not is_app_installed(repo_name):
        result = download_application(full_name)
    else:
        result = remove_application(full_name)

    # hide dialog and update installed state
    deselect_application()
    refresh_page()

    return result

# mouse control
mouse_group = displayio.Group(scale=SCALE)
root_group.append(mouse_group)
async def mouse_task() -> None:
    global selected_category, selected_application
    while True:
        if (mouse := adafruit_usb_host_mouse.find_and_init_boot_mouse()) is not None:
            mouse.x = DISPLAY_WIDTH // 2
            mouse.y = DISPLAY_HEIGHT // 2
            mouse_group.append(mouse.tilegrid)

            timeouts = 0
            previous_mouse_state = False
            while timeouts < 99:
                if mouse.update() is not None:
                    timeouts = 0
                    mouse_state = "left" in mouse.pressed_btns
                    if mouse_state and not previous_mouse_state:
                        if dialog_buttons.hidden:
                            if (clicked_cell := item_grid.which_cell_contains((mouse.x * SCALE, mouse.y * SCALE))) is not None:
                                select_application(clicked_cell[1] * PAGE_COLUMNS + clicked_cell[0])
                            elif not right_arrow.hidden and right_arrow.contains((mouse.x, mouse.y, 0)):
                                next_page()
                            elif not left_arrow.hidden and left_arrow.contains((mouse.x, mouse.y, 0)):
                                previous_page()
                            elif exit_tg.contains((mouse.x, mouse.y, 0)):
                                reset()
                            else:
                                for button in category_group:
                                    if button.contains((mouse.x, mouse.y)):
                                        select_category(button.label)
                                        break
                        else:
                            for button in dialog_buttons:
                                if button.contains((mouse.x, mouse.y, 0)):
                                    button.click()
                    previous_mouse_state = mouse_state
                else:
                    timeouts += 1
                await asyncio.sleep(1/30)

            mouse_group.remove(mouse.tilegrid)
        await asyncio.sleep(1)

async def keyboard_task() -> None:
    # flush input buffer
    while supervisor.runtime.serial_bytes_available:
        sys.stdin.read(1)

    while True:
        while (c := supervisor.runtime.serial_bytes_available) > 0:
            key = sys.stdin.read(c)
            if key == "\x1b":  # escape
                reset()
        await asyncio.sleep(1/30)

async def main() -> None:
    await asyncio.gather(
        asyncio.create_task(mouse_task()),
        asyncio.create_task(keyboard_task()),
    )

try:
    asyncio.run(main())
except KeyboardInterrupt:
    reset()
