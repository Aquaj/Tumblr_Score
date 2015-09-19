import sys, time, re, os, string
import argparse
import pickle

import pytumblr

import requests
from bs4 import BeautifulSoup

import multiprocessing
import multiprocessing.forking
from multiprocessing import Queue, Value, Lock


# client = pytumblr.TumblrRestClient(
#	 'uErEk0uFQF2JRlLDg5eDA2yBLrUf2J1jq6P9RxTxMTJesYX0Iu',
#	 'bRORrMhgu5uiqQI6jkRK4fmbZBQN3WDqeUmZjX9H6ULRVUJI4u',
#	 '9eiFTlrSFD6XkaKN7lvUmMUdFYiPGkP1a9rxPbQtpKCDXwuuJq',
#	 'WJQ1EbBC52fXV19zsgLd0GMoxlEfC0O8vYLjNAPcwhEa97MMFa'
# )

class _Popen(multiprocessing.forking.Popen):
    def __init__(self, *args, **kw):
        if hasattr(sys, 'frozen'):
            # We have to set original _MEIPASS2 value from sys._MEIPASS
            # to get --onefile mode working.
            os.putenv('_MEIPASS2', sys._MEIPASS)
        try:
            super(_Popen, self).__init__(*args, **kw)
        finally:
            if hasattr(sys, 'frozen'):
                # On some platforms (e.g. AIX) 'os.unsetenv()' is not
                # available. In those cases we cannot delete the variable
                # but only set it to the empty string. The bootloader
                # can handle this case.
                if hasattr(os, 'unsetenv'):
                    os.unsetenv('_MEIPASS2')
                else:
                    os.putenv('_MEIPASS2', '')

class Process(multiprocessing.Process):
    _Popen = _Popen

class Joss(Exception): pass

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
		if toDo>50:
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
				for l in soup.findAll("li", "note"):
					noteCount += 1
					p.value = (float(noteCount)/float(toDo))*100.0
					if "original_post" not in l['class']:
						if("reblog" in l['class']):
							reblogs+=1
							notes+=[[l.findAll("a", "tumblelog")[0].contents[0].encode('utf-8'), l.findAll("a", "source_tumblelog")[0].contents[0].encode('utf-8'), l.findAll("span")[0]["data-post-url"].split("/")[-1].encode('utf-8')]]
						if("reply" in l['class']):
							replies+=[[l.findAll("a")[1].contents[0].encode('utf-8'), l.findAll("span", "answer_content")[0].contents[0].encode('utf-8')]]
						if("more_notes_link_container" in l['class']):
							url="?"+l.findAll("a")[0]["onclick"].split("?")[1].split(',true')[0][:-1].encode('utf-8')		
					else:
						notes+=[[l.findAll("a")[1].contents[0].encode('utf-8'), l.findAll("a")[1].contents[0].encode('utf-8'), l.findAll("span")[0]["data-post-url"].split("/")[-1].encode('utf-8')]]
						raise Joss
				noteCount -= 1
		else:
			lp.acquire()
			flush()
			print "\n Using API to get notes -- That one case where the API isn't useless, wow."
			print " -- /!\ No influence analysis or graph can be provided under 50 notes. --\n"
			lp.release()
			while(True):
				for n in notesClient['notes']:
					noteCount += 1
					p.value = (float(noteCount)/float(toDo))*100.0
					if n['type']!="posted":
						if n['type']=="reblog":
							reblogs+=1
							notes += [[n['blog_name'],"", int(n['post_id'])]]
						if n['type']=="reply":
							replies+=[[n['blog_name'],n['reply_text']]]
					else:
						notes += [[n['blog_name'],"", int(n['post_id'])]]
						raise Joss
	except Joss:
		pass

	users = []

	for n in notes:
		if n[0] not in users:
			users += [n[0]]
	for n in notes:
		if n[1] not in users:
			n[1] = notes[-1][1]

	users = list(set(users))

	q.put_nowait(users)
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

def calcCentrality(db, ret, p, lp):

	def ssspb(G, s):
		S = []
		P = {}
		for v in G:
			P[v] = []
		sigma = dict.fromkeys(G, 0.0)	# sigma[v]=0 for v in G
		D = {}
		sigma[s] = 1.0
		D[s] = 0
		Q = [s]
		while Q:   # use BFS to find shortest paths
			v = Q.pop(0)
			S.append(v)
			Dv = D[v]
			sigmav = sigma[v]
			for w in G[v]:
				if w not in D:
					Q.append(w)
					D[w] = Dv + 1
				if D[w] == Dv + 1:   # this is a shortest path, count paths
					sigma[w] += sigmav
					P[w].append(v)  # predecessors
		return S, P, sigma

	def ssspl(G, s):
		seen = {}				  # level (number of hops) when seen in BFS
		level = 0				  # the current level
		nextlevel = {s:1}  # dict of nodes to check at next level
		while nextlevel:
			thislevel = nextlevel  # advance to next level
			nextlevel = {}		 # and start a new list (fringe)
			for v in thislevel:
				if v not in seen:
					seen[v] = level # set the level of vertex v
					for e in G[v]:
						nextlevel.update({e:0}) # add neighbors of v
					yield (v, level)
			level=level+1
		del seen

	def _accumulate_basic(betweenness, S, P, sigma, s):
		delta = dict.fromkeys(S, 0)
		while S:
			w = S.pop()
			coeff = (1.0 + delta[w]) / sigma[w]
			for v in P[w]:
			   	delta[v] += sigma[v] * coeff
			if w != s:
				betweenness[w] += delta[w]
		return betweenness

	nodes = db.keys()
	
	lp.acquire(True)
	flush()
	print " Detail of calculations:"
	lp.release()

	p.value = 0.0

	closeness = {}
	for n in nodes:
		sp = dict(ssspl(db, n))
		totsp = sum(sp.values())
		if totsp > 0.0 and len(nodes) > 1:
			closeness[n] = (len(sp)-1.0) / totsp
			# normalize to number of nodes-1 in connected part
			s = (len(sp)-1.0) / (len(nodes)-1)
			closeness[n] *= s
		else:
			closeness[n] = 0.0

	lp.acquire(True)
	flush()
	print "\t - Calculation of Closeness done."
	lp.release()
	
	p.value = 0.0
	betweenness = dict.fromkeys(nodes, 0.0)
	for s in nodes:
		p.value = (float(nodes.index(s)) / len(nodes) * 100.0)
		S, P, sigma = ssspb(db, s)
		betweenness = _accumulate_basic(betweenness, S, P, sigma, s)
	for s in nodes:
		betweenness[s] *=  1.0 / ((len(nodes) - 1) * (len(nodes) - 2))

	lp.acquire(True)
	flush()
	print "\t - Calculation of Betweenness done."
	lp.release()

	p.value = 50.0
	degree={}
	s=1.0/(len(nodes)-1.0)
	degree=dict((n,(d+1)*s) for n,d in ((n, len(db[n])) for n in nodes))

	lp.acquire(True)
	flush()
	print "\t - Calculation of Degree done."
	lp.release()

	ret.put_nowait(closeness)
	ret.put_nowait(betweenness)
	ret.put_nowait(degree)
	ret.put('STOP')
	ret.close()
	return

def populartags(cli, notes, p, q):
	tags = {}
	L = len(notes)
	for i in range(L):
		p.value = float(i)/float(L)*100.0
		n = notes[i]
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
	maxlength = len(src)
	progress = 0
	for u in src:
		db[u] = []
	for n in data:
		if n[0] not in db[n[1]]:
			db[n[1]] += [n[0]]
		progress += 1
		p.value = progress*1.0/maxlength*100.0
	q.put(db)
	q.close()
	return

if __name__=='__main__':

	multiprocessing.freeze_support()

	version = "0.9.9"

	corpus = ["the", "be", "to", "of", "and", "a", "in", "that", "have", "I", "it", "for", "not", "on", "with", "im" "he", "as", "you", "do", "at", "this", "but", "his", "by", "from", "they", "we", "say", "her", "she", "or", "an", "my", "one", "would", "there", "their", "what", "so", "out", "if", "who", "get", "which", "go", "me", "when", "make", "can", "like", "i", "is", "are", "all", "then", "u"]

	client = pytumblr.TumblrRestClient('uErEk0uFQF2JRlLDg5eDA2yBLrUf2J1jq6P9RxTxMTJesYX0Iu')

	parser = argparse.ArgumentParser(prog="Score v"+version, description="Note Analyzer for tumblr posts. If no arguments are provided, will run on http://breadstyx.tumblr.com/post/128187440953/")
	graphrelated = parser.add_argument_group('graph related')
	parser.add_argument("PostId", type=int, help="the ID of the post you want to analyze. ex: http://breadstyx.tumblr.com/post/<128187440953>/hey-there-fellow", nargs='?', default=128187440953)
	parser.add_argument("sourceBlog", type=str, help="the blog containing the post you want to analyze. ex: http://<breadstyx>.tumblr.com/post/128187440953/hey-there-fellow", nargs='?', default="breadstyx")
	parser.add_argument("-l","--logging", help="will log the notes as a readable file called readable_note_dump", action="store_true")
	parser.add_argument("-c", "--cleanup", help="cleans up by removing all dumps at the end of the program", action="store_true")
	parser.add_argument("-t","--tags", help="will the analyze user tags and display the tags and words most frequently used in tags of the post - /!\ Caution: can be quite long if no dump present.", action="store_true", default=False)
	graphrelated.add_argument("-v","--visualization", help="will create a GML file of notes so that Gelphi can vizualize the graph of reblogs", action="store_true")
	parser.add_argument("-nr","--no-refresh", help="toggle refreshing of notes off - notes will be read from previous dump : Do Not Use if there is no dump available", action="store_true")
	parser.add_argument("-nd","--no-dumping", help="the program will not make any dump files", action="store_true")
	parser.add_argument("-na","--no-analysis", help="toggle analysis of notes off", action="store_true")
	graphrelated.add_argument("-ni", "--no-influence", help ="toggle the analysis of users' influence on reblogs off and as such won't display the bloggers that had the most influence on the post", action="store_true")
	parser.add_argument("-ng", "--no-graph", help ="toggle off graph generation from notes - caution: graph-related options won't work if no dump exist", action="store_true")
	args = parser.parse_args()

	LOGGING = args.logging
	VISUALIZATION = args.visualization
	REGENERATE = not args.no_refresh
	ANALYSIS = not args.no_analysis
	GRAPH_GEN = not args.no_graph
	POPULAR_TAGS = args.tags
	EVALUATE_CENTRALITY = not args.no_influence
	CLEAN = args.cleanup
	NO_DUMPING = args.no_dumping

	id_post = args.PostId
	sourceBlog = args.sourceBlog

	dumpfile = "score_dump_"+str(id_post)
	notesdump = "notes_dump_"+str(id_post)
	tagsdump = "tags_dump_"+str(id_post)

	results = Queue()
	lockPrint = Lock()
	dummy = Lock()
	progress = Value('d', 0.0)
	trashLord = os.path.isfile(dumpfile)
	trashJudge = os.path.isfile(notesdump)
	trashStreetArtist = os.path.isfile(tagsdump)

	print "\n  --* TUMBLR SCORE - Note Analysis & User Influence v"+version+" *--  "

	if(REGENERATE or not trashJudge):

		if not REGENERATE:
			print "\n At least one fetching is required to perform the program."
		if trashJudge:
			print "\n A dump of this post's notes already exists. Are you sure you want to refresh it? To use it without refreshing it run :"
			print " python main.py"+((" "+str(id_post)+" "+sourceBlog)+" " if (id_post, sourceBlog) != (128187440953, "breadstyx") else " ")+"-nr\n"

		p1 = Process(target = loadingtime, args=(lockPrint, progress))
		p2 = Process(target = scrapping, args=(client, id_post, sourceBlog, progress, results, lockPrint))
		p2.start()
		p1.start()
		users = results.get()
		notes = results.get()
		replies = results.get()
		noteCount = results.get()
		p1.terminate()

		Dnotes = open(notesdump, 'w')
		pickle.dump([users, notes, replies, noteCount], Dnotes)
		Dnotes.close()

	else:
		Dnotes = open(notesdump, 'r')
		notesObj = pickle.load(Dnotes)
		users = notesObj[0]
		notes = notesObj[1]
		replies = notesObj[2]
		noteCount = notesObj[3]

	flush()
	print "\t"+str(len(notes))+" reblogs added to list !\n"
	flush()
	print "\tNotes composed of "+str(int(len(notes)*1.0/(noteCount*1.0)*100))+"% reblogs. ("+str(len(notes))+"/"+str(noteCount)+")\n"
	if len(replies)>0:
		print " Replies :"
		for r in replies:
			print " - "+r[0]+" said: "+r[1]
		print "\n",

	if LOGGING:
		flush()
		print " LOG - Writing a log in readable_note_dump"
		dump = open("readable_note_dump", 'w')
		for n in notes:
			dump.write(" reblogged from : ".join(n)+"\n")

	activate = (noteCount>=50)

	GRAPH_GEN = GRAPH_GEN and activate
	VISUALIZATION = VISUALIZATION and activate
	EVALUATE_CENTRALITY = EVALUATE_CENTRALITY and activate
	LOGGING = LOGGING and activate
	
	if GRAPH_GEN:
		if trashLord and REGENERATE:
			print "\n A dump of this posts' notes' graph already exists. Are you sure you want to refresh it? To use it without refreshing it run :"
			print " python main.py"+((" "+str(id_post)+" "+sourceBlog)+" " if (id_post, sourceBlog) != (128187440953, "breadstyx") else " ")+"-nr -ng\n"

		print " Reformatting data so it can be easily converted to Graph later."

		if REGENERATE or not trashLord:
			progress.value = 0.0
			p1 = Process(target = loadingtime, args=(dummy, progress))
			p2 = Process(target = new_db, args=(users, notes, results, progress))
			p2.start()
			p1.start()
			database = results.get()
			p1.terminate()
			flush()
			print("\tData formatted!\n")
			filedump = open(dumpfile, 'w')
			pickle.dump([database, noteCount, notes], filedump)
			filedump.close()
		else:
			print " Loading graph from "+dumpfile+"."
			filedump = open(dumpfile, 'r')
			args = pickle.load(filedump)
			database = args[0]
			noteCount = args[1]
			notes = args[2]
			filedump.close()
	elif (VISUALIZATION or EVALUATE_CENTRALITY) and trashLord:
			print " A dump exists and graph-related functionalities have been toggled on:\n\tLoading graph from "+dumpfile+"."
			filedump = open(dumpfile, 'r')
			args = pickle.load(filedump)
			database = args[0]
			noteCount = args[1]
			notes = args[2]
			filedump.close()

	if(LOGGING):
		print "\n LOG - Updating log in readable_note_dump"
		dump = open("readable_note_dump", 'w')
		for user in database.keys():
			if len(database[user])>0:
				dump.write(user + " had their post reblogged by : "+", ".join(database[user])+"\n")
			else:
				dump.write(user + " doesn't have any fRIENDS AND AS SUCH DOESNT HELP PROPAGATE MY POST.\n")
		for reply in replies:
			dump.write(reply[0] + " said : "+reply[1]+"\n")

	if (GRAPH_GEN or trashLord) and VISUALIZATION:
		output_nodes = output_edges = ""
		print " Writing a GML file for Gephi visualization."
		graphFile = open("score.gml", 'w')
		graphFile.write("graph\n[\n")
		for node in database.keys():
			output_nodes += "  node\n  [\n   id "+node+"\n   label "+node+"\n  ]\n"
			for edgeEnd in database[node]:
				output_edges += "  edge\n  [\n   source "+node+"\n   target "+edgeEnd+"\n  ]\n"
		graphFile.write(output_nodes)
		print "\t - Nodes written !"
		graphFile.write(output_edges)
		print "\t - Edges written !\n"
		graphFile.write("]")

	if ANALYSIS:

		if POPULAR_TAGS:
			if trashStreetArtist and REGENERATE:
				print " A dump of this posts' user tags already exists. Are you sure you want to refresh it? To use it without refreshing it run :"
				print " python main.py"+((" "+str(id_post)+" "+sourceBlog)+" " if (id_post, sourceBlog) != (128187440953, "breadstyx") else " ")+"-nr\n"

			print " Fetching tags."

			if REGENERATE or not trashStreetArtist:
				progress.value = 0.0
				p1 = Process(target = loadingtime, args=[dummy, progress])
				p2 = Process(target = populartags, args=(client, notes, progress, results))
				p1.start()
				p2.start()
				tags = results.get()
				progress.value = 100.0
				p1.terminate()
			
				flush()
				print "\n Pickling Tags in "+tagsdump+" to save time on next uses."
				filedump = open(tagsdump, 'w')
				pickle.dump(tags, filedump)
				filedump.close()
			else:
				print "\n Loading Tags from "+dumpfile+"."
				filedump = open(tagsdump, 'r')
				tags = pickle.load(filedump)
				filedump.close()

			wc = {}
			for tag in tags.keys():
				for w in tag.split():
					word = w.lower()
					for p in string.punctuation:
						word = word.replace(p, "")
					if word not in wc.keys():
						wc[word] = 0
					if word not in corpus:
						wc[word] += tags[tag]
			
			popTags = reversed([(i.encode('utf-8'), tags[i]) for i in sorted(tags, key=lambda x: tags[x])][-10:])
			flush()
			print "\n These tags were the most used on the post :"
			for tag in popTags:
				print "\t[#"+tag[0]+"] used "+str(tag[1])+" times."
			popWords = reversed([(i.encode('utf-8'), wc[i]) for i in sorted(wc, key=lambda x: wc[x])][-10:])
			print "\n These words were the most used on the post :"
			for word in popWords:
				print "\t\""+word[0]+"\" used "+str(word[1])+" times."

		if (GRAPH_GEN or trashLord) and EVALUATE_CENTRALITY:

			central = []

			print "\n Starting calculation of centrality."
			progress.value = 100.0
			p1 = Process(target = loadingtime, args=[lockPrint, progress])
			p2 = Process(target = calcCentrality, args=(database, results, progress, lockPrint))
			p2.start()
			p1.start()
			for i in iter(results.get, 'STOP'):
				central.append(i)
			p1.terminate()

			flush()
			print "\tCentrality values calculated!"

			print "\n Using centrality to establish who had the most influence on the notes.\n"
			winners = [[i for i in sorted(central[j], key=lambda x: central[j][x])][-10:] for j in range (len(central))]

			influence_scores = {}

			for table in winners:
				for user in table:
					if user not in influence_scores.keys():
						influence_scores[user] = 0	
					influence_scores[user] += table.index(user)+1

			print " Outputting influence list w/ scores. (arbitrary unit)\n"
			leaderboard = [(i, influence_scores[i]) for i in sorted(influence_scores, key=lambda x: influence_scores[x])]
			for score in reversed(leaderboard):
				print " \t"+str(len(leaderboard)-leaderboard.index(score))+" - "+str(score[0])+" - influence: "+str(score[1])

	if CLEAN:
		print "\n Cleaning up all dumps !"
		regexdump = "^(score|notes|tags)_dump_[0-9]{12}$"
		i = 0
		for f in os.listdir("."):
			if NO_DUMPING:
				regexdump = regexdump.replace("[0-9]{12}", str(id_post))
			if re.search(regexdump, f):
				os.remove(os.path.join(".", f))
				i += 1
		print " Removed "+str(i)+" dumpfiles !"
