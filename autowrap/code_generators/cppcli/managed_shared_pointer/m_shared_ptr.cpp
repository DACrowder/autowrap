﻿#pragma once

#include "m_shared_ptr.hpp"

template <class T>
public ref class m_shared_ptr sealed
{
    std::shared_ptr<T>* pPtr;
private:
    bool isDisposed;
public:
    m_shared_ptr() 
        : pPtr(new std::shared_ptr<T>()) 
    {
        isDisposed = false;
    }

    m_shared_ptr(T* t) : m_shared_ptr() {
        pPtr = new std::shared_ptr<T>(t);
    }

    m_shared_ptr(std::shared_ptr<T> t) {
        pPtr = new std::shared_ptr<T>(t);
    }

    m_shared_ptr(const m_shared_ptr<T>% t) {
        pPtr = new std::shared_ptr<T>(*t.pPtr);
    }

    !m_shared_ptr() {
        delete pPtr;
    }

    ~m_shared_ptr() {
        this->!m_shared_ptr();
        isDisposed = true;
    }

    operator std::shared_ptr<T>() {
        return *pPtr;
    }

    m_shared_ptr<T>% operator=(T* ptr) {
        delete pPtr;
        pPtr = new std::shared_ptr<T>(ptr);
        return *this;
    }

    T* operator->() {
        return (*pPtr).get();
    }

    void reset() {
        pPtr->reset();
    }
};