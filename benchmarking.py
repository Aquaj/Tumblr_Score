import networkx
from multiprocessing import Process, Lock, Queue
from multiprocessing.queues import SimpleQueue
import time

values = [(500, 500), (250, 500), (500, 250), (1000, 500), (1500, 1500), (5000, 5000)]

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
			e = (i%inp, i%out)
			if e not in Score.edges():
				Score.add_edges_from([e])
		# print Score.edges()

		iset = set([i for i,o in Score.edges()])
		iset = set(iset)
		oset = set([o for i,o in Score.edges()])
		oset = set(oset)

		V = len(Score.nodes())
		E = len(Score.edges())
		D = degree(Score)
		I = len(iset)
		O = len(oset)

		print " Graph - "+writedata([V,E,D,I,O])

		start=time.clock()
		networkx.betweenness_centrality(Score)
		end=time.clock()
		T = end - start
		print "Done."

		data = open("banchmark_data", 'a')
		data.write(writedata([V,E,D,I,O,T])+"\n")
		data.close()