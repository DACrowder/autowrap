﻿#pragma once

#include <memory>

template <class T>
public ref class m_shared_ptr sealed
{
    std::shared_ptr<T>* pPtr;
private:
    bool isDisposed;
public:
    m_shared_ptr();
    m_shared_ptr(T* t);
    m_shared_ptr(std::shared_ptr<T> t);
    m_shared_ptr(const m_shared_ptr<T>% t);
    !m_shared_ptr();
    ~m_shared_ptr();
    operator std::shared_ptr<T>();
    m_shared_ptr<T>% operator=(T* ptr);
    T* operator->();
    void reset();
};