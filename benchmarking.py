import networkx
from multiprocessing import Process, Lock, Queue, Value
from multiprocessing.queues import SimpleQueue
import time

values = [(500, 500), (250, 500), (500, 250), (1500, 1500), (5000, 5000), (1000, 500)]

def countSteps(p):
	while True:
		p.value+=1

def writedata(values):
	output = ""
	for v in values:
		output += "".join([" " for tab in range(8-len(str(v)))])+str(v)
	return output+"\n"

def degree(G):
	d = 0.0
	for n in G.nodes():
		d += G.degree(n)
	return d/len(G.nodes())

if __name__ == "__main__":
	for analysisV in values:

		inp = analysisV[0]
		out = analysisV[1]

		Score = networkx.MultiDiGraph()
		for i in range(1,5000):
			e = (i%out, i%inp)
			if e not in Score.edges():
				Score.add_edges_from([e])
		# print Score.edges()

		oset = set([i for i,o in Score.edges()])
		oset = set(oset)
		iset = set([o for i,o in Score.edges()])
		iset = set(iset)

		V = len(Score.nodes())
		E = len(Score.edges())
		D = degree(Score)
		O = len(oset)
		I = len(iset)

		print " Graph - "+writedata([V,E,D,O,I])
		time = Value('i', 0)
		p1 = Process(target = countSteps, args=[time])
		p1.start()
		networkx.betweenness_centrality(Score)
		p1.terminate()
		print "Done."

		data = open("banchmark_data", 'a')
		data.write(writedata([V,E,I,O,time.value]))
		data.close()