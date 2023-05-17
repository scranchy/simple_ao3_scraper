#!/usr/bin/python3

# This is a simple script for parsing a bunch of fic metadata from
# a provided Ao3 search, and then stuffing it into a json. 
# I personally use this to do analysis in R Markdown, but you, dear friend
# can do whatever the hell you want. 

import sys, getopt, time
import json
import requests
from bs4 import BeautifulSoup


test_url = "https://archiveofourown.org/works?commit=Sort+and+Filter&work_search%5Bsort_column%5D=revised_at&work_search%5Bother_tag_names%5D=&work_search%5Bexcluded_tag_names%5D=&work_search%5Bcrossover%5D=F&work_search%5Bcomplete%5D=&work_search%5Bwords_from%5D=100&work_search%5Bwords_to%5D=&work_search%5Bdate_from%5D=&work_search%5Bdate_to%5D=&work_search%5Bquery%5D=&work_search%5Blanguage_id%5D=en&tag_id=%E3%83%A2%E3%83%96%E3%82%B5%E3%82%A4%E3%82%B3100+%7C+Mob+Psycho+100"

test_url_contains_anonymous = "https://archiveofourown.org/works?commit=Sort+and+Filter&work_search%5Bsort_column%5D=revised_at&include_work_search%5Brating_ids%5D%5B%5D=13&include_work_search%5Brelationship_ids%5D%5B%5D=10483645&work_search%5Bother_tag_names%5D=&work_search%5Bexcluded_tag_names%5D=&work_search%5Bcrossover%5D=&work_search%5Bcomplete%5D=&work_search%5Bwords_from%5D=&work_search%5Bwords_to%5D=&work_search%5Bdate_from%5D=&work_search%5Bdate_to%5D=&work_search%5Bquery%5D=&work_search%5Blanguage_id%5D=&tag_id=%E3%83%A2%E3%83%96%E3%82%B5%E3%82%A4%E3%82%B3100+%7C+Mob+Psycho+100"

def _request_ao3(url, page=1):
    """
    Makes a request to ao3, returns structured metadata list.
    """
    success = False
    while not success:
        try:
            time.sleep(5) #need to wait 5 secs before req ao3 per TOS
            r = requests.get(url)
            if r.status_code != 200:
                success = False
            else:
                return _parse_ao3_result_list(r.text)
        except Exception as e:
            print(str(e))


def _stat_parse_helper(stat_object, class_name):
    find_stat = stat_object.find('dd', class_=class_name)
    find_stat = int(find_stat.text.replace(',', '')) if find_stat else 0
    return find_stat


def _parse_ao3_result_list(html_str):
    """
    Uses beautiful soup to transform html into json with relevant metadata.
    Things I care about: title, author, id, rating, tags, pairings, description, warnings, 
    word count, chapters, kudos, hits, comments, date published, date updated
    """
    soup = BeautifulSoup(html_str, 'html.parser')
    work_index_group = soup.find('ol', class_="work index group")
    works = work_index_group.find_all('li', class_="work")

    jsons = []
    for work in works:
        
        # basics
        header = work.div
        h4 = header.h4
        link = h4.a
        author = link.find_next().text
        id_ = link.get('href')
        title = link.string
        is_anon = False
        is_orphan = 'orphan_account' == author
        
        # logic gets screwed up b/c anonymous doesn't link
        # this is a hack, but orphan_account should just work since it links
        if 'Anonymous' in h4.text and 'Anonymous' not in title:
            is_anon = True
            author = 'Anonymous'

        # wrangle the required tags
        required_tags = header.find('ul', class_="required-tags")
        tag_lis = required_tags.find_all('li')
        rating = tag_lis[0].a.text
        warnings = tag_lis[1].a.text.split(', ')
        category = tag_lis[2].a.text.split(', ')
        is_wip = tag_lis[3].a.text == "Work in Progress"

        # unfortunately, this is the best date we can do from search
        last_updated = header.find('p', class_="datetime").text

        # wrangle the freeform tags
        tags_commas = work.find('ul', class_="tags commas")
        relationships = tags_commas.find_all('li', class_="relationships")
        is_slash = False
        if relationships:
            relationships = [r.a.text for r in relationships]
            is_slash = True if any('/' in r for r in relationships) else False
        freeforms = tags_commas.find_all('li', class_="freeforms")
        if freeforms:
            freeforms = [f.a.text for f in freeforms]
        
        bq = work.find('blockquote', class_="userstuff summary")
        summary = bq.text        
        
        # gran series meta from summary and break it down
        series = work.find('ul', class_="series")
        is_series = False
        all_series = []
        if series:
            is_series = True
            series_ls = series.find_all('li')
            for s in series_ls:
                installment = int(s.strong.text.replace(',', '')) # wild if this is needed
                series_id = s.a.get('href')
                series_name = s.a.text
                series_meta = {
                    'installment': installment,
                    'seriesId': series_id,
                    'seriesName': series_name,
                }
                all_series.append(series_meta)

        stats_all = work.find('dl', class_="stats")
        language = stats_all.find('dd', class_="language").text
        words = _stat_parse_helper(stats_all, 'words')
        
        chapters = stats_all.find('dd', class_="chapters").text.split('/')
        cur_chapters = int(chapters[0].replace(',', ''))
        intended_chapters = chapters[1]
        
        # stats stuff
        kudos = _stat_parse_helper(stats_all, 'kudos')
        hits = _stat_parse_helper(stats_all, 'hits')
        comments = _stat_parse_helper(stats_all, 'comments')
        collections = _stat_parse_helper(stats_all, 'collections')
        # i have decided that i do not care about collection meta
        # but if i did, it would go here
        bookmarks = _stat_parse_helper(stats_all, 'bookmarks')

        # put that shit together
        jsons.append({
            "title": title,
            "author": author,
            "isAnon": is_anon,
            "isOrphan": is_orphan,
            "id": id_,
            "rating": rating,
            "warnings": warnings,
            "category": category,
            "isWip": is_wip,
            "lastUpdated": last_updated,
            "relationships": relationships,
            "isSlash": is_slash,
            "freeforms": freeforms,
            "summary": summary,
            "isSeries": is_series,
            "seriesMeta": all_series,
            "language": language,
            "words": words,
            "currentChapters": cur_chapters,
            "intendedChapters": intended_chapters,
            "kudos": kudos,
            "hits": hits,
            "comments": comments,
            "bookmarks": bookmarks,
            "collections": collections,
        })

    return jsons


def main():
    # todo ani, make this page
    r = requests.get(test_url_contains_anonymous)
    html = r.text

    result_list = _parse_ao3_result_list(html)
    
    with open('outfile.json', 'w') as outfile:
        json.dump({'data': result_list}, outfile,indent=4)

if __name__ == "__main__":
    main()


# todo ani, commandline run logic with any search
# def main(argv):
#    search_url = ''
#    outputfile = ''
#    try:
#       opts, args = getopt.getopt(argv,"hu:o:",["url=","ofile="])
#    except getopt.GetoptError:
#       print ('test.py -u <search_url> -o <outputfile>')
#       sys.exit(2)
#    for opt, arg in opts:
#       if opt == '-h':
#          print ('test.py -u <search_url> -o <outputfile>')
#          sys.exit()
#       elif opt in ("-u", "--url"):
#          search_url = arg
#       elif opt in ("-o", "--ofile"):
#          outputfile = arg
#    print ('Input file is "', search_url)
#    print ('Output file is "', outputfile)
#    # do stuff with parsing here


# if __name__ == "__main__":
#    main(sys.argv[1:])
