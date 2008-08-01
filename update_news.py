#!/usr/bin/python2.4

import os.path
import re, logging
from time import time, gmtime, asctime, strftime
from calendar import timegm
from cPickle import dump, load
from optparse import OptionParser

import feedparser
feedparser.USER_AGENT = "VIFF Homepage Generator +http://viff.dk/"

from genshi.template import TemplateLoader


def fetch_and_cache(url, directory=None, file=None):
    if directory is None:
        directory = ".feed-cache"

    if not os.path.isdir(directory):
        logging.info("Creating directory %s" % directory)
        os.mkdir(directory)

    if file is None:
        parts = re.split('[^a-z0-9.]+', url)
        file = "-".join(parts)
        logging.debug("Cache built from URL: '%s'" % file)

    file = os.path.join(directory, file)

    try:
        mtime = gmtime(os.path.getmtime(file))
    except OSError:
        mtime = gmtime(0)
    logging.debug("Last modification time: %s" % asctime(mtime))

    data = feedparser.parse(url, modified=mtime)
    logging.debug("Feed status: %d" % data.status)

    if data.status == 304:
        fp = None
        try:
            fp = open(file, 'r')
            data = load(fp)
        finally:
            if fp is not None:
                fp.close()
    else:
        fp = None
        try:
            fp = open(file, 'w')
            dump(data, fp)
        finally:
            if fp is not None:
                fp.close()

    logging.debug("Returning feed with %d entries" % len(data.entries))
    return data

def age(time_tuple):
    deltas = [(60*60*24*7*365, 'years'),
              (60*60*24*7*30, 'months'),
              (60*60*24*7, 'weeks'),
              (60*60*24, 'days'),
              (60*60, 'hours'),
              (60, 'minutes'),
              (1, 'seconds')]

    # Correction for daylight saving. Feedparser seems to return a
    # struct_time with the tm_isdst flag set to 1 if local daylight
    # savings is in effect. This hopefully corrects this extra offset.
    daylight_offset = time_tuple[8] * 3600
    difference = time() - (timegm(time_tuple) - daylight_offset)
    for delta, text in deltas:
        if difference > 2*delta:
            break

    return "%d %s" % (round(difference / delta), text)

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-v", "--verbose",
                      help="verbose output.",
                      action="store_true",
                      dest="verbose")
    parser.add_option("-q", "--quiet",
                      help="quiet output.",
                      action="store_false",
                      dest="verbose")

    parser.set_defaults(verbose=False)

    (options, args) = parser.parse_args()

    if options.verbose:
        level = logging.DEBUG
    else:
        level = logging.WARN

    logging.getLogger().setLevel(level)

    logging.info("Fetching data")
    repository_data = fetch_and_cache("http://hg.viff.dk/viff/atom-log")
    viff_devel_data = fetch_and_cache("http://rss.gmane.org/messages/excerpts/"
                                      "gmane.comp.cryptography.viff.devel")

    logging.info("Calculating ages")
    for entry in repository_data.entries:
        entry.age = age(entry.updated_parsed)
    for entry in viff_devel_data.entries:
        entry.age = age(entry.updated_parsed)

    #tip_age = age(repository_data.entries[0].updated_parsed)
    #now = strftime("%Y-%m-%d %H:%M UTC", gmtime())

    logging.info("Rewriting Gmane links")
    for entry in viff_devel_data.entries:
        entry.link = entry.link.replace("http://permalink.gmane.org/",
                                        "http://article.gmane.org/")


    count = 4
    repository_entries = repository_data.entries[:count]
    viff_devel_entries = [e for e in viff_devel_data.entries
                          if e.author != "viff-devel< at >viff.dk"][:count]

    logging.info("Rendering news.html")
    loader = TemplateLoader(['.'])
    tmpl = loader.load('news.xml')
    stream = tmpl.generate(repository=repository_entries,
                           viff_devel=viff_devel_entries)
    out = open('_news.html', 'w')
    out.write(stream.render('html'))
    out.close()
    os.rename('_news.html', 'news.html')

    logging.info("Finished")
