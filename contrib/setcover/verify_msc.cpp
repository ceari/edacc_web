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
	ifstream instance(argv[1]);
	vector<int> ids;
	string line;
	getline(instance, line);
	istringstream istr(line);
	int id;
	while(istr >> id) {
		ids.push_back(id);
	}
	ifstream output(argv[2]);
	while(getline(output, line) && line[0] != 'v');
	istringstream istr2(line);
	vector<int> got_ids;
	int assignment;
	istr2 >> line;
	while(istr2 >> assignment) {
		getline(instance, line);
		if (assignment > 0) {
			istringstream istr(line);
			int solverID;
			istr >> solverID;
			cout << solverID << endl;
			while(istr >> id) {
				got_ids.push_back(id);
			}
		}
	}
	sort(ids.begin(), ids.end());
	sort(got_ids.begin(), got_ids.end());
	got_ids.erase(unique(got_ids.begin(), got_ids.end()), got_ids.end());
	assert(got_ids == ids);
	return 0;
}
