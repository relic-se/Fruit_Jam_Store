#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2025 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: MIT
import json
import os
from pathlib import Path
import re

from github import Github
from mdutils.mdutils import MdUtils

DATABASE_FILE = "applications.json"
MARKDOWN_FILE = "README.md"

def main():
    db_dir = Path(__file__).parent

    # delete readme
    if os.path.isfile(db_dir / MARKDOWN_FILE):
        os.remove(db_dir / MARKDOWN_FILE)

    # read applications database
    print("Reading database")
    with open(db_dir / DATABASE_FILE, "r") as f:
        database = json.load(f)

    # connect with GitHub API
    print("Connecting with GitHub Web API")
    gh = Github()

    # setup README
    print("Beginning markdown file generation")
    md = MdUtils(file_name=str(db_dir / MARKDOWN_FILE))
    md.new_header(
        level=1,
        title="Applications Database",
    )
    md.new_line("Interested in contributing your Fruit Jam application? Read the [documention](./CONTRIBUTING.md) to learn more.")
    md.new_line()

    for category in database.keys():
        repositories = database[category]

        print("Generating category: {:s}".format(category))
        md.new_header(
            level=2,
            title=category,
        )

        for repo_slug in repositories:
            # get repository
            print("Reading repository: {:s}".format(repo_slug))
            repo = gh.get_repo(repo_slug)
            raw_url = "https://raw.githubusercontent.com/{:s}/main".format(
                repo.full_name,
                repo.default_branch
            )

            # read repository readme (for title and screenshot)
            print("Reading README.md")
            readme_contents = repo.get_readme().decoded_content.decode("utf-8")
            title = re.search(r'^# (.*)$', readme_contents, re.MULTILINE)
            title = title.group(1) if title is not None else repo.name
            icon = None

            # read Fruit Jam OS metadata
            print("Reading metadata.json: ", end="")
            try:
                if metadata_file := repo.get_contents("metadata.json"):
                    metadata = json.loads(metadata_file.decoded_content.decode("utf-8"))
                    title = metadata["title"]
                    if "icon" in metadata:
                        icon = metadata["icon"]
            except Exception as e:
                if hasattr(e, "message"):
                    print(e.message)
                else:
                    print(e)
            else:
                print("Success!")
            
            # add application title
            md.new_header(
                level=3,
                title=(
                    "![{:s} icon]({:s}/{:s}) {:s}".format(
                        title,
                        raw_url,
                        icon,
                        title
                    ) if icon is not None else title
                ),
            )

            # add project description
            if repo.description:
                md.new_line(repo.description)
                md.new_line()

            # find screenshot in readme contents
            screenshot = re.search(r'!\[([^\]]*)\]\(([^\)]+)\)', readme_contents)
            if screenshot is not None:
                md.new_line(md.new_inline_image(
                    text=screenshot.group(1),
                    path=raw_url + "/" + screenshot.group(2),
                ))
                md.new_line()

            # create details table
            details = {}

            if repo.homepage:
                details["Website"] = repo.homepage
            
            print("Reading build/metadata.json: ", end="")
            try:
                if metadata_file := repo.get_contents("build/metadata.json"):
                    metadata = json.loads(metadata_file.decoded_content.decode("utf-8"))
                    if "guide_url" in metadata:
                        details["Playground Guide"] = "[{:s}]({:s})".format(metadata["guide_url"], metadata["guide_url"])
            except Exception as e:
                if hasattr(e, "message"):
                    print(e.message)
                else:
                    print(e)
            else:
                print("Success!")

            details["Latest Release"] = "[Download]({:s}/releases/latest)".format(repo.html_url)
            details["Code Repository"] = "[{:s}]({:s})".format(repo.full_name, repo.html_url)
            details["Author"] = "[{:s}]({:s})".format(repo.owner.name, repo.owner.html_url)

            details = list(map(lambda key: "{:s}: {:s}".format(key, details[key]), details))
            md.new_list(details)
    
    # save file
    print("Saving markdown into {:s}".format(MARKDOWN_FILE))
    md.create_md_file()

    # close connection to GitHub API
    print("Closing GitHub Web API connection")
    gh.close()

    print("{:s} generation completed!".format(MARKDOWN_FILE))

if __name__ == "__main__":
    main()
