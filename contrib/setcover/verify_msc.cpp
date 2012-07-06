#include <iostream>
#include <assert.h>
#include <algorithm>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
using namespace std;

int main(int argc, char **argv) {
	if (argc != 3) {
		printf("usage: %s <instance file name> <output file name>\n", argv[0]);
		return 1;
	}
	ifstream output(argv[2]);
	string line;
	while(getline(output, line) && line[0] != 'v');
	do {
		istringstream istr2(line);
		ifstream instance(argv[1]);
		vector<int> ids;
		getline(instance, line);
		istringstream istr(line);
		int id;
		while(istr >> id) {
			ids.push_back(id);
		}
		vector<int> got_ids;
		int assignment;
		istr2 >> line;
		bool first = true;
		while(istr2 >> assignment) {
			getline(instance, line);
			if (assignment > 0) {
				istringstream istr(line);
				int solverID;
				istr >> solverID;
				if (first) first = false;
				else cout << " ";
				cout << solverID;
				while(istr >> id) {
					got_ids.push_back(id);
				}
			}
		}
		cout << endl;
		sort(ids.begin(), ids.end());
		sort(got_ids.begin(), got_ids.end());
		got_ids.erase(unique(got_ids.begin(), got_ids.end()), got_ids.end());
		assert(got_ids == ids);
	}while(getline(output, line) && line[0] == 'v');
	return 0;
}
