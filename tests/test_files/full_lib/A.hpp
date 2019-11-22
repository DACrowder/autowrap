#include <vector>
#include <string>
#include <utility>
#include <map>
#include <boost/shared_ptr.hpp>

#ifndef HEADER_A
#define HEADER_A

enum testA {
    AA, AAA
};


class Aklass {
    public:
        int i_;
        Aklass(int i): i_(i) { };
        Aklass(const Aklass & i): i_(i.i_) { };

    enum KlassE { A1, A2, A3};
};

class MZProvider {
    public:
        double getMZ() { return mz; }
        void setMZ(double i) { mz = i; }
    private:
        double mz;
};

class RangeManager {
    public:
        int getNext(int i) { return i-1; }
};


class A_second : public MZProvider, public RangeManager {
    public:
        int i_;
        A_second(int i): i_(i) { };
        A_second(const A_second & i): i_(i.i_) { };
        void callA2() {i_++;};
        int getNext(int i) override { return RangeManager::getNext(_i) + i; }
        int getNext() { return RangeManager::getNext(_i); }
};

#endif
