# pylint: disable=global-statement,redefined-outer-name
import csv
import glob
import json

import hydra
import yaml
from flask import Flask, jsonify, redirect, render_template, send_from_directory
from flask_frozen import Freezer
from flaskext.markdown import Markdown
from omegaconf import DictConfig

# ------------- SERVER CODE -------------------->

app = Flask(__name__)
freezer = Freezer(app)
markdown = Markdown(app)

# MAIN PAGES


@app.route("/")
def index():
    return redirect("/index.html")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.config["site_data_path"], "favicon.ico")


# TOP LEVEL PAGES


@app.route("/index.html")
def home():
    site_data = app.config["site_data"]
    data = {"config": site_data["config"]}
    data["readme"] = open("README.md").read()
    data["committee"] = site_data["committee"]["committee"]
    return render_template("index.html", **data)


@app.route("/help.html")
def about():
    site_data = app.config["site_data"]
    data = {"config": site_data["config"]}
    data["FAQ"] = site_data["faq"]["FAQ"]
    return render_template("help.html", **data)


@app.route("/papers.html")
def papers():
    site_data = app.config["site_data"]
    data = {"config": site_data["config"]}
    data["papers"] = site_data["papers"]
    return render_template("papers.html", **data)


@app.route("/paper_vis.html")
def paper_vis():
    site_data = app.config["site_data"]
    data = {"config": site_data["config"]}
    return render_template("papers_vis.html", **data)


@app.route("/calendar.html")
def schedule():
    by_uid = app.config["by_uid"]
    site_data = app.config["site_data"]
    data = {"config": site_data["config"]}
    data["day"] = {
        "speakers": site_data["speakers"],
        "highlighted": [
            format_paper(by_uid["papers"][h["UID"]]) for h in site_data["highlighted"]
        ],
    }
    return render_template("schedule.html", **data)


@app.route("/workshops.html")
def workshops():
    site_data = app.config["site_data"]
    data = {"config": site_data["config"]}
    data["workshops"] = [
        format_workshop(workshop) for workshop in site_data["workshops"]
    ]
    return render_template("workshops.html", **data)


def extract_list_field(v, key):
    value = v.get(key, "")
    if isinstance(value, list):
        return value
    else:
        return value.split("|")


def format_paper(v):
    list_keys = ["authors", "keywords", "sessions"]
    list_fields = {}
    for key in list_keys:
        list_fields[key] = extract_list_field(v, key)

    return {
        "UID": v["UID"],
        "title": v["title"],
        "forum": v["UID"],
        "authors": list_fields["authors"],
        "keywords": list_fields["keywords"],
        "abstract": v["abstract"],
        "TLDR": v["abstract"],
        "recs": [],
        "sessions": list_fields["sessions"],
        # links to external content per poster
        "pdf_url": v.get("pdf_url", ""),  # render poster from this PDF
        "code_link": "https://github.com/Mini-Conf/Mini-Conf",  # link to code
        "link": "https://arxiv.org/abs/2007.12238",  # link to paper
    }


def format_workshop(v):
    list_keys = ["authors"]
    list_fields = {}
    for key in list_keys:
        list_fields[key] = extract_list_field(v, key)

    return {
        "id": v["UID"],
        "title": v["title"],
        "organizers": list_fields["authors"],
        "abstract": v["abstract"],
    }


# ITEM PAGES


@app.route("/poster_<poster>.html")
def poster(poster):
    by_uid = app.config["by_uid"]
    uid = poster
    v = by_uid["papers"][uid]
    site_data = app.config["site_data"]
    data = {"config": site_data["config"]}
    data["paper"] = format_paper(v)
    return render_template("poster.html", **data)


@app.route("/speaker_<speaker>.html")
def speaker(speaker):
    by_uid = app.config["by_uid"]
    uid = speaker
    v = by_uid["speakers"][uid]
    site_data = app.config["site_data"]
    data = {"config": site_data["config"]}
    data["speaker"] = v
    return render_template("speaker.html", **data)


@app.route("/workshop_<workshop>.html")
def workshop(workshop):
    uid = workshop
    by_uid = app.config["by_uid"]
    v = by_uid["workshops"][uid]
    site_data = app.config["site_data"]
    data = {"config": site_data["config"]}
    data["workshop"] = format_workshop(v)
    return render_template("workshop.html", **data)


@app.route("/chat.html")
def chat():
    site_data = app.config["site_data"]
    data = {"config": site_data["config"]}
    return render_template("chat.html", **data)


# FRONT END SERVING


@app.route("/papers.json")
def paper_json():
    site_data = app.config["site_data"]
    json = []
    for v in site_data["papers"]:
        json.append(format_paper(v))
    return jsonify(json)


@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static", path)


@app.route("/serve_<path>.json")
def serve(path):
    site_data = app.config["site_data"]
    return jsonify(site_data[path])


# --------------- DRIVER CODE -------------------------->
# Code to turn it all static


@freezer.register_generator
def generator():
    site_data = app.config["site_data"]
    for paper in site_data["papers"]:
        yield "poster", {"poster": str(paper["UID"])}
    for speaker in site_data["speakers"]:
        yield "speaker", {"speaker": str(speaker["UID"])}
    for workshop in site_data["workshops"]:
        yield "workshop", {"workshop": str(workshop["UID"])}

    for key in site_data:
        yield "serve", {"path": key}


def setup_paths(site_data_path):
    site_data = {}
    by_uid = {}
    extra_files = ["README.md"]
    # Load all for your sitedata one time.
    for f in glob.glob(site_data_path + "/*"):
        extra_files.append(f)
        name, typ = f.split("/")[-1].split(".")
        if typ == "json":
            site_data[name] = json.load(open(f))
        elif typ in {"csv", "tsv"}:
            site_data[name] = list(csv.DictReader(open(f)))
        elif typ == "yml":
            site_data[name] = yaml.load(open(f).read(), Loader=yaml.SafeLoader)

    for typ in ["papers", "speakers", "workshops"]:
        by_uid[typ] = {}
        for p in site_data[typ]:
            by_uid[typ][p["UID"]] = p

    print("Data Successfully Loaded")
    return site_data, extra_files, by_uid


@hydra.main(version_base=None, config_path="configs", config_name="site")
def hydra_main(cfg: DictConfig):

    site_data_path = cfg.site_data_path
    site_data, extra_files, by_uid = setup_paths(site_data_path)
    app.config["config"] = cfg
    app.config["site_data"] = site_data
    app.config["by_uid"] = by_uid
    app.config["site_data_path"] = site_data_path

    if cfg.build:
        freezer.freeze()
    else:
        app.run(port=cfg.port, debug=cfg.debug, extra_files=extra_files)


if __name__ == "__main__":
    hydra_main()  # pylint: disable=no-value-for-parameter
