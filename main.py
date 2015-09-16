import sys, time, re
import argparse
import pickle

import pytumblr

import requests
from bs4 import BeautifulSoup

from multiprocessing import Process, Queue, Value, Lock

import networkx


# client = pytumblr.TumblrRestClient(
#     'uErEk0uFQF2JRlLDg5eDA2yBLrUf2J1jq6P9RxTxMTJesYX0Iu',
#     'bRORrMhgu5uiqQI6jkRK4fmbZBQN3WDqeUmZjX9H6ULRVUJI4u',
#     '9eiFTlrSFD6XkaKN7lvUmMUdFYiPGkP1a9rxPbQtpKCDXwuuJq',
#     'WJQ1EbBC52fXV19zsgLd0GMoxlEfC0O8vYLjNAPcwhEa97MMFa'
# )

version = "0.9"

client = pytumblr.TumblrRestClient('uErEk0uFQF2JRlLDg5eDA2yBLrUf2J1jq6P9RxTxMTJesYX0Iu')

class Joss(Exception): pass

parser = argparse.ArgumentParser(prog="Score v"+version, description="Note Analyzer for tumblr posts. If no arguments are provided, will run on http://breadstyx.tumblr.com/post/128187440953/")
graphrelated = parser.add_argument_group('graph related')
parser.add_argument("PostId", type=int, help="the ID of the post you want to analyze. ex: http://breadstyx.tumblr.com/post/<128187440953>/hey-there-fellow", nargs='?', default=128187440953)
parser.add_argument("sourceBlog", type=str, help="the blog containing the post you want to analyze. ex: http://<breadstyx>.tumblr.com/post/128187440953/hey-there-fellow", nargs='?', default="breadstyx")
parser.add_argument("-l","--logging", help="will log the notes as a readable file called readable_note_dump", action="store_true")
graphrelated.add_argument("-v","--visualization", help="will create a GML file of notes so that Gelphi can vizualize the graph of reblogs", action="store_true")
parser.add_argument("-nr","--no-refresh", help="toggle refreshing of notes off - notes will be read from previous dump : Do Not Use if there is no dump available", action="store_true")
parser.add_argument("-na","--no-analysis", help="toggle analysis of notes off", action="store_true")
parser.add_argument("-nt","--no-tags", help="toggle the analysis of user tags off and as such wont display the tags frequently used on the post", action="store_true")
graphrelated.add_argument("-ni", "--no-influence", help ="toggle the analysis of users' influence on reblogs off and as such won't display the bloggers that had the most influence on the post", action="store_true")
parser.add_argument("-ng", "--no-graph", help ="toggle off graph generation from notes - caution: graph-related options won't work", action="store_true")
args = parser.parse_args()

LOGGING = args.logging
VISUALIZATION = args.visualization
REGENERATE = not args.no_refresh
ANALYSIS = not args.no_analysis
GRAPH_GEN = not args.no_graph
POPULAR_TAGS = not args.no_tags
EVALUATE_CENTRALITY = not args.no_influence

id_post = args.PostId
sourceBlog = args.sourceBlog

dumpfile = "score_dump_"+str(id_post)

def scrapping(cli, postID, blogSource, p, q, lp):
	url = ""
	urlbis = "" 
	notes=[]
	replies=[]
	reblogs = 0
	noteCount = 0

	notesClient = cli.posts(blogSource+'.tumblr.com', id=postID, notes_info=True)['posts'][0]
	toDo = notesClient['note_count']
	try:
		if len(notesClient['notes'])==50:
			i = 0
			while True:
				while notesClient['notes'][i]["type"] != "reblog":
					i += 1
				page = requests.get(notesClient['notes'][i]["blog_url"]+"post/"+notesClient['notes'][i]["post_id"])
				soup = BeautifulSoup(page.text, 'html.parser')
				if len(soup.findAll("a", "more_notes_link")) != 0:
					break
				i += 1
			addendum_url = soup.findAll("a", "more_notes_link")[0]["onclick"].split('GET\',\'/')[1].split('?from')[0]
			theURL = notesClient['notes'][i]["blog_url"]+addendum_url

			lp.acquire()
			flush()
			print "\n Scrapping pages to get the notes.  -- Fuck The API"
			lp.release()
			while(True):
				page = requests.get(theURL+url)
				soup = BeautifulSoup(page.text, 'html.parser')
				for l in soup.findAll("li"):
					noteCount += 1
					p.value = ((noteCount-1)*1.0/toDo*1.0)*100.0
					if "original_post" not in l['class']:
						if("reblog" in l['class']):
							reblogs+=1
							notes+=[[l.findAll("a", "tumblelog")[0].contents[0].encode('utf-8'), l.findAll("a", "source_tumblelog")[0].contents[0].encode('utf-8'), l.findAll("span")[0]["data-post-url"].split("/")[-1].encode('utf-8')]]
						if("reply" in l['class']):
							replies+=[[l.findAll("a")[1].contents[0].encode('utf-8'), l.findAll("span", "answer_content")[0].contents[0].encode('utf-8')]]
					else:
						raise Joss
				try:
					urlbis=url
					url="?"+soup.findAll("a", "more_notes_link")[0]["onclick"].split("?")[1].split(',true')[0][:-1].encode('utf-8')
				except IndexError:
					lp.acquire()
					print "We're not supposed to be here at Aaaaaaall - lalalalilalaaaa"
					lp.release()
					raise Joss
		else:
			lp.acquire()
			flush()
			print "\n Using API to get notes -- That one case where the API isn't useless, wow."
			print " -- No influence analysis or graph can be provided under 50 notes. --\n"
			lp.release()
			while(True):
				for n in notesClient['notes']:
					noteCount += 1
					p.value = (noteCount*1.0/toDo*1.0)*100.0
					if n['type']!="posted":
						if n['type']=="reblog":
							reblogs+=1
					if n['type']=="reply":
							replies+=[[n['blog_name'],n['reply_text']]]
					else:
						raise Joss
	except Joss:
		lp.acquire()
		flush()
		print "\t"+str(reblogs)+" reblogs added to list !\n"
		flush()
		print "\tNotes composed of "+str(int(reblogs*1.0/(noteCount*1.0)*100))+"% reblogs. ("+str(reblogs)+"/"+str(noteCount)+")\n"
		if len(replies)>0:
			print " Replies :"
			for r in replies:
				print " - "+str(r[0])+" said: "+str(r[1])
			print "\n",
		lp.release()

	q.put_nowait(list(set([n[0] for n in notes])))
	q.put_nowait(notes)
	q.put_nowait(replies)
	q.put_nowait(noteCount)
	return


def flush():
	print "\r\t\t\t\t\t\t\t\t\r",

def loadingtime(lock, perc=None):
	j = 0
	while True:
		time.sleep(0.5)
		if lock.acquire():
			flush()
			sys.stdout.write("\r\t\tLoading"+ ("".join(["." for counter in range(j%4)]) if (perc == None) else (" "+str(int(perc.value))+"% " + \
																																			("/" if (j%4 == 0) else \
																																			("-" if (j%4 == 1) else \
																																			("\\" if (j%4 == 2) else \
																																			("|")))))))
			lock.release()
			j+=1

def calcCentrality(G, ret, lp):
	
	lp.acquire(True)
	flush()
	print " Detail of calculations:"
	lp.release()
	
	ya = networkx.closeness_centrality(G)
	lp.acquire(True)
	flush()
	print "\t - Calculation of Closeness done."
	lp.release()
	
	yo = networkx.betweenness_centrality(G)
	lp.acquire(True)
	flush()
	print "\t - Calculation of Betweenness done."
	lp.release()
	
	yi = networkx.degree_centrality(G)
	lp.acquire(True)
	flush()
	print "\t - Calculation of Degree done."
	lp.release()
	
	yu = networkx.load_centrality(G)
	lp.acquire(True)
	flush()
	print "\t - Calculation of Load done."
	lp.release()
	ret.put_nowait(ya)
	ret.put_nowait(yo)
	ret.put_nowait(yi)
	ret.put_nowait(yu)
	ret.put('STOP')
	ret.close()
	return

def populartags(cli, notes, p, q):
	tags = {}
	for n in notes:
		p.value = float(notes.index(n))/float(len(notes))*100.0
		user = n[0]
		waf = n[2]
		tagsUser = cli.posts(user+".tumblr.com", id=waf)['posts'][0]['tags']
		for tag in tagsUser:
			if tag not in tags.keys():
				tags[tag] = 0
			tags[tag] += 1
	q.put_nowait(tags)
	q.close()
	return

def new_db(src, data, q, p):
	db = {}
	maxlength = len(src)*len(data)
	progress = 0
	for user in src:
		db[user] = []
		for n in sorted(data):
			save = p.value
			if (n[1] == user):
				db[user] += [n[0]]
			progress += 1	
			p.value = progress*1.0/maxlength*100.0
	q.put(db)
	q.close()
	return

if __name__=='__main__':

	results = Queue()
	lockPrint = Lock()
	dummy = Lock()
	progress = Value('d', 0.0)

	print "\n  --* TUMBLR SCORE - Note Analysis & User Influence v"+version+" *--  "

	if(REGENERATE):

		if True:
			p1 = Process(target = loadingtime, args=(lockPrint, progress))
			p2 = Process(target = scrapping, args=(client, id_post, sourceBlog, progress, results, lockPrint))
			p2.start()
			p1.start()
			users = results.get()
			notes = results.get()
			replies = results.get()
			noteCount = results.get()
			p1.terminate()

			d = open("debug", 'w')
			pickle.dump([users, notes, noteCount], d)
			d.close()
		else:
			d = open("debug", 'r')
			a = pickle.load(d)
			users = a[0]
			notes = a[1]
			replies = a[2]
			noteCount = a[3]
			d.close()

		activate = (len(client.posts(sourceBlog+'.tumblr.com', id=id_post, notes_info=True)['posts'][0]['notes'])>=50)

		GRAPH_GEN = GRAPH_GEN and activate
		VISUALIZATION = VISUALIZATION and activate
		ANALYSIS = ANALYSIS and activate
		EVALUATE_CENTRALITY = EVALUATE_CENTRALITY and activate
		LOGGING = LOGGING and activate

		if LOGGING:
			flush()
			print " LOG - Writing a log in readable_note_dump"
			dump = open("readable_note_dump", 'w')
			for n in notes:
				dump.write(" reblogged from : ".join(n)+"\n")

		if GRAPH_GEN:
			print " Reformatting data so it can be easily converted to Graph later."

			progress.value = 0.0
			p1 = Process(target = loadingtime, args=(dummy, progress))
			p2 = Process(target = new_db, args=(users, notes, results, progress))
			p2.start()
			p1.start()
			database = results.get()
			p1.terminate()
			flush()
			print("\tData formatted!")

			Score = networkx.MultiDiGraph()
			Score.add_nodes_from(database.iterkeys())
			print " Creating Score Graph using NetworkX."
			for source in database.iterkeys():
				for target in database[source]:
					Score.add_edge(source, target)

			print " Pickling Score in "+dumpfile+" to save time on next uses."
			filedump = open(dumpfile, 'w')
			pickle.dump([Score, noteCount, notes], filedump)
			filedump.close()


		if(LOGGING):
			print "\n LOG - Updating log in readable_note_dump"
			dump = open("readable_note_dump", 'w')
			for user in database.keys():
				if len(database[user])>0:
					dump.write(user + " had their post reblogged by : "+", ".join(database[user])+"\n")
				else:
					dump.write(user + " doesn't have any fRIENDS AND AS SUCH DOESNT HELP PROPAGATE MY POST.\n")

		if GRAPH_GEN and VISUALIZATION:
			print " Writing a GML file for Gephi visualization."
			graphFile = open("score.gml", 'w')
			graphFile.write("graph\n[\n")
			for node in database.keys():
				graphFile.write("  node\n  [\n   id "+node+"\n   label "+node+"\n  ]\n")
			print "\t - Nodes written !"
			for node in database.keys():
				for edgeEnd in database[node]:
					graphFile.write("  edge\n  [\n   source "+node+"\n   target "+edgeEnd+"\n  ]\n")
			print "\t - Edges written !\n"
			graphFile.write("]")

	if ANALYSIS:

		print " Loading Score from pickle."
		filedump = open(dumpfile, 'r')
		(Score, noteCount, notes) = pickle.load(filedump)
		filedump.close()
		central = []

		if POPULAR_TAGS:

			print "\n Fetching tags."

			progress.value = 0.0
			p1 = Process(target = loadingtime, args=[dummy, progress])
			p2 = Process(target = populartags, args=(client, notes, progress, results))
			p1.start()
			p2.start()
			tags = results.get()
			p1.terminate()
			popTags = reversed([(i.encode('utf-8'), tags[i]) for i in sorted(tags, key=lambda x: tags[x])][-10:])
			print " These tags were the most used on the post :"
			for tag in popTags:
				print "\t\""+tag[0]+"\" used "+str(tag[1])+" times."

		if GRAPH_GEN and EVALUATE_CENTRALITY:

			print "\n Starting calculation of centrality."

			p1 = Process(target = loadingtime, args=[lockPrint])
			p2 = Process(target = calcCentrality, args=(Score, results, lockPrint))
			p2.start()
			p1.start()
			for i in iter(results.get, 'STOP'):
				central.append(i)
			p1.terminate()
			dumpfile = open("centrality_dump", 'w')
			pickle.dump(central, dumpfile)
			dumpfile.close()
		else:
			dumpfile = open("centrality_dump", 'r')
			central = pickle.load(dumpfile)
			dumpfile.close()

		flush()
		print "\tCentrality values calculated!"

		print "\n Using centrality to establish who had the most influence on the notes.\n"
		winners = [[i for i in sorted(central[j], key=lambda x: central[j][x])][-10:] for j in range (4)]

		influence_scores = {}

		for table in winners:
			for user in table:
				if user not in influence_scores.keys():
					influence_scores[user] = 0	
				influence_scores[user] += table.index(user)

		print " Outputting influence list w/ scores. (arbitrary unit)\n"
		leaderboard = [(i, influence_scores[i]) for i in sorted(influence_scores, key=lambda x: influence_scores[x])]
		for score in reversed(leaderboard):
			print " \t"+str(len(leaderboard)-leaderboard.index(score))+" - "+str(score[0])+" - influence: "+str(score[1])