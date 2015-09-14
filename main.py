import requests
from bs4 import BeautifulSoup
import pickle
import networkx
from multiprocessing import Process, Lock, Queue, Value
from multiprocessing.queues import SimpleQueue
import sys, time, re
import pytumblr

# client = pytumblr.TumblrRestClient(
#     'uErEk0uFQF2JRlLDg5eDA2yBLrUf2J1jq6P9RxTxMTJesYX0Iu',
#     'bRORrMhgu5uiqQI6jkRK4fmbZBQN3WDqeUmZjX9H6ULRVUJI4u',
#     '9eiFTlrSFD6XkaKN7lvUmMUdFYiPGkP1a9rxPbQtpKCDXwuuJq',
#     'WJQ1EbBC52fXV19zsgLd0GMoxlEfC0O8vYLjNAPcwhEa97MMFa'
# )

client = pytumblr.TumblrRestClient('uErEk0uFQF2JRlLDg5eDA2yBLrUf2J1jq6P9RxTxMTJesYX0Iu')

class Joss(Exception): pass

ANALYSIS = True
REGENERATE = False
LOGGING = True
VISUALIZATION = True
EVALUATE_CENTRALITY = True

id_post = sys.argv[1] if len(sys.argv)>1 else 128187440953
sourceBlog = sys.argv[2] if len(sys.argv)>2 else "breadstyx"

dumpfile = "score_dump"

def scrapping(cli, postID, blogSource, p, q, l, lp):
	url = ""
	urlbis = "" 
	notes=[]
	reblogs = 0
	noteCount = 0

	notesClient = cli.posts(blogSource+'.tumblr.com', id=postID, notes_info=True)['posts'][0]
	toDo = notesClient['note_count']

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
	try:
		while(True):
			page = requests.get(theURL+url)
			soup = BeautifulSoup(page.text, 'html.parser')
			for l in soup.findAll("li"):
				noteCount += 1
				p.value = (noteCount*1.0/toDo*1.0)*100.0
				if("reblog" in l['class']):
					if "original_post" not in l['class']:
						reblogs+=1
						try:
							notes+=[[str(l.findAll("a", "tumblelog")[0].contents[0]), str(l.findAll("a", "source_tumblelog")[0].contents[0])]]
						except:
							print l['class']
					else:
						raise Joss
			try:
				urlbis=url
				url="?"+str(soup.findAll("a", "more_notes_link")[0]["onclick"].split("?")[1].split(',true')[0][:-1])
			except IndexError:
				lp.acquire()
				print "We're not supposed to be here at Aaaaaaall - lalalalilalaaaa"
				lp.release()
				raise Joss
	except Joss:
			lp.acquire()
			flush()
			print "\t"+str(reblogs)+" reblogs added to list !\n"
			flush()
			print "\tNotes composed of "+str(int(reblogs*1.0/(noteCount*1.0)*100))+"% reblogs.\n"
			lp.release()
	
	q.put_nowait(list(set([n[0] for n in notes])))
	q.put_nowait(notes)
	q.put_nowait(noteCount)
	return


def flush():
	print "\r\t\t\t\t\t\t\t\t\r",

def loadingtime(lock, perc=None):
	j = 0
	while True:
		time.sleep(0.5)
		lock.acquire(True)
		flush()
		sys.stdout.write("\r\t\tLoading"+ ("".join(["." for counter in range(j%4)]) if (perc == None) else (" "+str(int(perc.value))+"% " + \
																																			("/" if (j%4 == 0) else \
																																			("-" if (j%4 == 1) else \
																																			("\\" if (j%4 == 2) else \
																																			("|")))))))
		lock.release()
		j+=1

def calcCentrality(G, p, ret, l, l2):
	l.acquire(True)
	flush()
	print " Detail of calculations:"
	ya = networkx.closeness_centrality(G)
	l2.acquire(True)
	flush()
	print "\t - Calculation of Closeness done."
	p.value = 1.0
	l2.release()
	yo = networkx.betweenness_centrality(G)
	l2.acquire(True)
	flush()
	print "\t - Calculation of Betweenness done."
	ret.put_nowait(yo)
	ret.put_nowait(ya)
	l2.release()
	yi = networkx.degree_centrality(G)
	l2.acquire(True)
	flush()
	print "\t - Calculation of Degree done."
	ret.put_nowait(yi)
	l2.release()
	yu = networkx.load_centrality(G)
	l2.acquire(True)
	flush()
	print "\t - Calculation of Load done."
	ret.put_nowait(yu)
	l2.release()
	ret.put('STOP')
	l.release()
	ret.close()
	return

def fragperc(G, p):
	pS = 0
	E = float(len(G.edges()))
	V = float(len(G.nodes()))
	while(p.value > 0.0):
		for p1 in range(len(G.edges())):
			p.value = float(p1)
			time.sleep(0.05)
			pS = p1
	return



def new_db(src, data, q, l, p):
	db = {}
	l.acquire(True)
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
	l.release()
	return

if __name__=='__main__':

	results = Queue()
	lock = Lock()
	lockPrint = Lock()
	dummy = Lock()
	progress = Value('d', 0.0)

	print "\n  --* TUMBLR SCORE - Note Analysis & User Influence v0.5 *--  "

	if(REGENERATE):

		if True:
			p1 = Process(target = loadingtime, args=(lockPrint, progress))
			p2 = Process(target = scrapping, args=(client, id_post, sourceBlog, progress, results, lock, lockPrint))
			p2.start()
			time.sleep(0.2)
			p1.start()
			lock.acquire(True)
			users = results.get()
			notes = results.get()
			noteCount = results.get()
			time.sleep(.1)
			lock.release()
			p1.terminate()

			d = open("debug", 'w')
			pickle.dump([users, notes, noteCount], d)
			d.close()
		else:
			d = open("debug", 'r')
			a = pickle.load(d)
			users = a[0]
			notes = a[1]
			noteCount = a[2]
			d.close()


		if(LOGGING):
			flush()
			print " LOG - Writing a log in readable_note_dump"
			dump = open("readable_note_dump", 'w')
			for n in notes:
				dump.write(" reblogged from : ".join(n)+"\n")

		print " Reformatting data so it can be easily converted to Graph later."

		progress.value = 0.0
		p1 = Process(target = loadingtime, args=(dummy, progress))
		p1.start()
		p2 = Process(target = new_db, args=(users, notes, results, lock, progress))
		p2.start()
		time.sleep(10)
		lock.acquire(True)
		database = results.get()
		time.sleep(.1)
		lock.release()
		p1.terminate()
		flush()
		print("\tData formatted!")


		if(LOGGING):
			print "\n LOG - Writing a log in readable_db_dump"
			dump = open("readable_db_dump", 'w')
			for user in database.keys():
				if len(database[user])>0:
					dump.write(user + " had their post reblogged by : "+", ".join(database[user])+"\n")
				else:
					dump.write(user + " doesn't have any fRIENDS AND AS SUCH DOESNT HELP PROPAGATE MY POST.\n")


		Score = networkx.MultiDiGraph()
		Score.add_nodes_from(database.iterkeys())
		print " Creating Score Graph using NetworkX."
		for source in database.iterkeys():
			for target in database[source]:
				Score.add_edge(source, target)

		if(VISUALIZATION):
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

		print " Pickling Score in "+dumpfile+" to save time on next uses."
		filedump = open(dumpfile, 'w')
		pickle.dump([Score, noteCount], filedump)
		filedump.close()

	if ANALYSIS:

		print " Loading Score from pickle."
		filedump = open(dumpfile, 'r')
		(Score, noteCount) = pickle.load(filedump)
		filedump.close()
		central = []

		print "\n Starting calculation of centrality."

		if(EVALUATE_CENTRALITY):

			progress.value = 0.0
			p1 = Process(target = loadingtime, args=(lockPrint, progress))
			p1.start()
			p2 = Process(target = calcCentrality, args=(Score, progress, results, lock, lockPrint))
			p2.start()
			p3 = Process(target = fragperc, args=(Score, progress))
			p3.start()
			lock.acquire(True)
			for i in iter(results.get, 'STOP'):
				central.append(i)
			time.sleep(.1)
			lock.release()
			p1.terminate()
			p3.terminate()
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
		winners = [[i for i in sorted(central[2], key=lambda x: central[2][x])][-10:] for j in range (4)]

		influence_scores = {}

		for table in winners:
			for user in table:
				influence_scores[user] = 0
		for table in winners:
			for user in table:
				influence_scores[user] += table.index(user)

		print " Outputting influence list w/ scores. (arbitrary unit)\n"
		leaderboard = [(i, influence_scores[i]) for i in sorted(influence_scores, key=lambda x: influence_scores[x])]
		for score in reversed(leaderboard):
			print " \t"+str(len(leaderboard)-leaderboard.index(score))+" - "+str(score[0])+" - influence: "+str(score[1])